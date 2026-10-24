"""Primer SFT (task M4 §1, TRAINING.md §5, ADR-023): full fine-tune, loss on the answers only.

    python -m ks.train.sft --config configs/train/sft.yaml [--set key=value ...]

One process does one attempt:
  1. fetch and tokenize the primer, refusing any example that shows an eval position;
  2. resume from the newest complete checkpoint under <root>/ckpt, if any;
  3. train with wall-clock checkpoints (model, optimizer, data position), each copied to
     <root>/ckpt in a background thread, and a short greedy probe of the RL prompt at each one
     (format and legal rate on dev500 positions: the T8 question, TRAINING.md §5);
  4. save the final model in bf16, with the original architecture and tokenizer files, to
     <root>/final/merged (what `ks eval --ckpt` and GRPO's `init_ckpt` load), then delete
     the optimizer-state checkpoints.
On SIGTERM (a preemption) it flushes metrics, leaves a marker in <out> and exits 143; the next
attempt resumes. Inside a ks VM the paths come from KS_GCS_PREFIX; on the laptop everything is
local (`--root`), which runs the same checkpoint code.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import threading
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Annotated, Any

import chess
import typer

from ks.chess import prompt as kpr
from ks.chess import rewards as kr
from ks.cloud.config import REPO
from ks.data.manifest import git_sha
from ks.data.primer import read_shards
from ks.eval import profile as prof
from ks.train import ckpt as kc
from ks.train import metrics as km
from ks.train import sft_data as sd
from ks.train.config import SftConfig, load_sft
from ks.train.grpo import fetch, now_iso, run_root, versions

TOKENIZE_BATCH = 2048
# files of the original snapshot that save_pretrained doesn't write: tokenizer, chat template,
# processor configs (vLLM reads them for the VLM class even when it serves text only)
_SNAPSHOT_FILES = re.compile(r".*\.(json|jinja|txt|model)$")
_WEIGHT_FILES = {"config.json", "model.safetensors.index.json", "generation_config.json"}


def _tokenize_shard(args: tuple[str, str, dict[str, Any], str, int | None]) -> dict[str, list]:
    path, model_path, kwargs, end, limit = args
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    tok = AutoTokenizer.from_pretrained(model_path)
    out: dict[str, list] = {"input_ids": [], "labels": [], "length": [], "task": [], "keys": []}
    batch: list[dict[str, Any]] = []

    def flush() -> None:
        part = sd.tokenize(tok, batch, kwargs, end)
        for k, v in part.items():
            out[k] += v
        out["keys"] += [e.get("keys", []) for e in batch]
        batch.clear()

    for i, ex in enumerate(read_shards([Path(path)])):
        if limit is not None and i >= limit:
            break
        batch.append(ex)
        if len(batch) >= TOKENIZE_BATCH:
            flush()
    if batch:
        flush()
    return out


def load_examples(
    cfg: SftConfig, p: prof.Profile, model_path: str, work: Path, log: Callable[[str], None]
) -> tuple[Any, dict[str, Any]]:
    """The tokenized primer as a datasets.Dataset in training order, and its summary."""
    from datasets import Dataset  # type: ignore[import-not-found]
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    from ks.data.blocklist import Blocklist
    from ks.eval.sets import SETS_DIR

    src = cfg.data if not cfg.data.startswith("gs://") else cfg.data.rstrip("/") + "/"
    local = fetch(src, work / "data" / Path(cfg.data.rstrip("/")).name)
    shards = sorted(Path(local).glob("shard-*.jsonl.zst"))
    if not shards:
        raise SystemExit(f"no primer shards in {cfg.data}")
    tok = AutoTokenizer.from_pretrained(model_path)
    first = next(read_shards(shards[:1]))
    end = sd.end_of_turn(tok, first, p.chat_template_kwargs)
    # `examples` (smoke tests) takes the first N in shard order: at most N from each shard, cut after
    jobs = [(str(s), model_path, p.chat_template_kwargs, end, cfg.examples) for s in shards]
    cols: dict[str, list] = {"input_ids": [], "labels": [], "length": [], "task": [], "keys": []}
    with ProcessPoolExecutor(min(len(jobs), os.cpu_count() or 1)) as ex:
        for part in ex.map(_tokenize_shard, jobs):
            for k in cols:
                cols[k] += part[k]
    if cfg.examples is not None:
        cols = {k: v[: cfg.examples] for k, v in cols.items()}
    blocked = Blocklist.load(SETS_DIR).keys
    hits = sd.contamination_hits(({"keys": k} for k in cols["keys"]), blocked)
    if hits:
        raise SystemExit(f"{hits} primer examples show an eval position; refusing to train")
    keep = [i for i, n in enumerate(cols["length"]) if n <= cfg.max_length]
    dropped = len(cols["length"]) - len(keep)
    summary = sd.summary(
        [cols["length"][i] for i in keep],
        [cols["labels"][i] for i in keep],
        [cols["task"][i] for i in keep],
    )
    summary |= {"dropped_over_max_length": dropped, "end_of_turn": end}
    order = sd.step_order([cols["length"][i] for i in keep], cfg.step_examples, cfg.seed)
    idx = [keep[i] for i in order]
    ds = Dataset.from_dict(
        {
            "input_ids": [cols["input_ids"][i] for i in idx],
            "labels": [cols["labels"][i] for i in idx],
        }
    )
    log(
        f"{summary['examples']:,} examples, {summary['tokens']:,} tokens "
        f"({summary['loss_tokens']:,} loss tokens), {dropped} over max_length dropped"
    )
    return ds, summary


def snapshot(p: prof.Profile) -> str:
    from huggingface_hub import snapshot_download  # type: ignore[import-not-found]

    assert p.hf_repo, f"{p.name} is not an open model"
    return snapshot_download(p.hf_repo, revision=p.revision)


def set_trainable(model: Any, pattern: str | None) -> int:
    """Train every language-model parameter (or those matching `pattern`); never the vision tower."""
    rx = re.compile(pattern) if pattern else None
    n = 0
    for name, param in model.named_parameters():
        on = "visual" not in name and (rx is None or rx.search(name) is not None)
        param.requires_grad_(on)
        n += param.numel() if on else 0
    if not n:
        raise RuntimeError(f"no trainable parameters (train_params={pattern!r})")
    return n


class Probe:
    """Greedy answers to a few dev500 RL prompts: is the RL format still there? (TRAINING.md §5)"""

    def __init__(self, cfg: SftConfig, p: prof.Profile, tok: Any) -> None:
        from ks.eval import sets

        self.p, self.tok, self.max_new = p, tok, cfg.probe_max_tokens
        puzzles = sets.spread(sets.load_puzzles("dev500"), cfg.probe_prompts)
        self.items = []
        for pz in puzzles:
            pos = pz.positions[0]
            b = chess.Board(pos["fen"])
            text = tok.apply_chat_template(
                kpr.messages(b, p.think, p.legal_list),
                tokenize=False,
                add_generation_prompt=True,
                **p.chat_template_kwargs,
            )
            target = kr.Target(b, chess.Move.from_uci(pos["solution_uci"]), pos["is_last"])
            self.items.append((tok(text, add_special_tokens=False)["input_ids"], target))

    def __call__(self, model: Any) -> dict[str, Any]:
        import torch  # type: ignore[import-not-found]

        was_training = model.training
        model.eval()
        fmt = legal = correct = tags = 0
        texts = []
        t = time.monotonic()
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16):
            for ids, target in self.items:
                x = torch.tensor([ids], device=model.device)
                y = model.generate(
                    input_ids=x,
                    attention_mask=torch.ones_like(x),
                    max_new_tokens=self.max_new,
                    do_sample=False,
                    use_cache=True,
                )
                text = self.tok.decode(y[0, len(ids) :], skip_special_tokens=True)
                r = kr.score(text, target, self.p.require_think)
                fmt += bool(r.format)
                legal += r.parsed.status == "ok"
                correct += bool(r.sparse)
                tags += "<answer>" in text
                texts.append(text)
        if was_training:
            model.train()
        n = len(self.items)
        return {
            "format": fmt / n,
            "legal": legal / n,
            "move_acc": correct / n,
            "answer_tag": tags / n,
            "seconds": round(time.monotonic() - t, 1),
            "examples": texts[:4],
        }


class Uploader:
    """Copies each saved checkpoint to <root>/ckpt in a background thread, one at a time, then
    deletes the older local ones. A copy cut off by a preemption has no _COMPLETE marker and is
    never resumed from (ks.train.ckpt)."""

    def __init__(self, store: kc.Store, root: str, keep: int, log: Callable[[str], None]) -> None:
        self.store, self.root, self.keep, self.log = store, root, keep, log
        self.thread: threading.Thread | None = None

    def wait(self) -> None:
        if self.thread is not None:
            self.thread.join()
            self.thread = None

    def start(self, local: Path) -> None:
        self.wait()

        def run() -> None:
            t = time.monotonic()
            try:
                n = kc.push(self.store, local, self.root, self.keep)
            except Exception as e:  # the next checkpoint tries again
                self.log(f"{local.name}: copy to {self.root} FAILED ({e}); training on")
                return
            self.log(f"{local.name}: {n} files to {self.root} in {time.monotonic() - t:.0f} s")
            for old in local.parent.glob("checkpoint-*"):
                if old != local and old.is_dir():
                    shutil.rmtree(old, ignore_errors=True)

        self.thread = threading.Thread(target=run, name="ckpt-upload", daemon=True)
        self.thread.start()


def save_final(model: Any, snapshot_dir: str, dest: Path) -> None:
    """bf16 weights with the base model's config, tokenizer and processor files, so vLLM and GRPO
    load it like the base model."""
    import torch  # type: ignore[import-not-found]

    snap = Path(snapshot_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for f in snap.iterdir():
        if f.is_file() and _SNAPSHOT_FILES.fullmatch(f.name) and f.name not in _WEIGHT_FILES:
            shutil.copyfile(f, dest / f.name)
    model.to(torch.bfloat16)
    model.save_pretrained(str(dest))
    # The base model's config, verbatim: the architecture is unchanged, and save_pretrained's
    # copy differs in serialisation (dtype fields, use_cache) and in the special-token ids that
    # SFTTrainer aligns with the tokenizer's. The checkpoint differs from the base in weights only.
    shutil.copyfile(snap / "config.json", dest / "config.json")
    gen = snap / "generation_config.json"
    if gen.exists():
        shutil.copyfile(gen, dest / gen.name)
    else:  # the base has none; vLLM then stops on the tokenizer's eos, as for the base
        (dest / gen.name).unlink(missing_ok=True)


def main(
    config: Annotated[str, typer.Option(help="configs/train/<sft>.yaml")],
    set_: Annotated[list[str] | None, typer.Option("--set", help="key=value overrides")] = None,
    out: Annotated[
        Path | None, typer.Option(help="Results dir (pushed to GCS in a ks VM); default $KS_OUT.")
    ] = None,
    root: Annotated[
        str | None, typer.Option(help="Checkpoint/final root; default from KS_GCS_PREFIX.")
    ] = None,
    work: Annotated[Path, typer.Option(help="Local scratch for checkpoints and models.")] = Path(
        "/tmp/ks-work"
    ),
) -> None:
    import torch  # type: ignore[import-not-found]
    import transformers  # type: ignore[import-not-found]
    from transformers import AutoConfig, AutoTokenizer, TrainerCallback  # type: ignore[import-not-found]
    from trl import SFTConfig, SFTTrainer  # type: ignore[attr-defined]

    cfg, overrides = load_sft(config, set_)
    out = out or Path(os.environ.get("KS_OUT", "out"))
    attempt = int(os.environ.get("KS_ATTEMPT", "1"))
    price = float(os.environ.get("KS_PRICE_PER_HOUR", "0") or 0)
    root_uri = run_root(root, out)
    ckpt_root = f"{root_uri}/ckpt"
    store = kc.store_for(root_uri)
    gcs_out = os.environ.get("KS_GCS_PREFIX")
    work.mkdir(parents=True, exist_ok=True)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TENSORBOARD_LOGGING_DIR", str(out / "tb" / f"attempt-{attempt}"))
    log = lambda s: typer.echo(f"[sft {cfg.name}] {now_iso()} {s}", err=True)  # noqa: E731

    clock = km.CostClock(price, km.spent_before(out / "metrics", attempt))
    steps_log = km.Jsonl(out / "metrics" / f"attempt-{attempt}.jsonl")
    probe_log = km.Jsonl(out / "metrics" / f"probe-attempt-{attempt}.jsonl")
    info_path = out / "run" / f"attempt-{attempt}.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)

    def push_out() -> None:
        if gcs_out:
            from ks.cloud import gcs

            try:
                gcs.push(out, f"{gcs_out}/out")
            except Exception as e:  # a failed push must not kill training
                log(f"push of {out} failed: {e}")

    def on_sigterm(signum: int, frame: Any) -> None:
        log(f"signal {signum}: leaving a marker and exiting (the next attempt resumes)")
        (out / f"sigterm-attempt-{attempt}").write_text(now_iso())
        push_out()
        os._exit(143)

    signal.signal(signal.SIGTERM, on_sigterm)

    p = prof.load(cfg.model)
    path = snapshot(p)
    ds, data_summary = load_examples(cfg, p, path, work, log)
    manifest = REPO / "manifests" / f"primer_{Path(cfg.data.rstrip('/')).name}.json"
    mdata = json.loads(manifest.read_text()) if manifest.exists() else {}
    info: dict[str, Any] = {
        "run_id": os.environ.get("KS_RUN_ID", cfg.name),
        "attempt": attempt,
        "git_sha": git_sha(),
        "image": os.environ.get("KS_IMAGE"),
        "machine": os.environ.get("KS_MACHINE"),
        "zone": os.environ.get("KS_ZONE"),
        "price_per_hour": price,
        "config": cfg.model_dump(),
        "config_hash": cfg.hash(),
        "overrides": overrides,
        "data": {"primer_sha256": mdata.get("sha256"), **data_summary},
        "seed": cfg.seed,
        "versions": versions(),
        "started": now_iso(),
    }
    info_path.write_text(json.dumps(info, indent=1))

    archs = AutoConfig.from_pretrained(path).architectures or ["AutoModelForCausalLM"]
    arch = getattr(transformers, archs[0])  # Qwen3.5 loads as the full VLM class, as in GRPO
    # fp32 master weights (bf16 autocast), cast on the GPU: a CPU copy in fp32 OOMed the laptop
    model = arch.from_pretrained(path, dtype=torch.float32, device_map={"": 0})
    trainable = set_trainable(model, cfg.train_params)
    tok = AutoTokenizer.from_pretrained(path)
    probe = Probe(cfg, p, tok)
    log(f"model {path}: {trainable:,} trainable parameters; config {cfg.hash()}, attempt {attempt}")

    args = SFTConfig(
        output_dir=str(work / "trainer"),
        num_train_epochs=cfg.epochs,
        learning_rate=cfg.learning_rate,
        lr_scheduler_type=cfg.lr_scheduler,
        warmup_steps=cfg.warmup_ratio,  # a float in [0, 1) is a ratio of the total steps
        weight_decay=cfg.weight_decay,
        max_grad_norm=cfg.max_grad_norm,
        per_device_train_batch_size=cfg.micro_batch,
        gradient_accumulation_steps=cfg.grad_accum,
        train_sampling_strategy="sequential",  # the dataset is already in step order (ADR-023)
        bf16=True,
        gradient_checkpointing=cfg.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=None,  # examples over cfg.max_length were dropped above
        packing=False,
        dataset_kwargs={"skip_prepare_dataset": True},  # tokenized, with labels
        logging_steps=1,
        report_to=["tensorboard"],
        save_strategy="no",  # checkpoints by wall clock, from the callback below
        save_total_limit=None,
        seed=cfg.seed,
        data_seed=cfg.seed,
    )
    t0 = time.monotonic()
    trainer: Any = SFTTrainer(model=model, args=args, train_dataset=ds, processing_class=tok)
    info |= {"init_seconds": round(time.monotonic() - t0, 1), "trainable_params": trainable}
    info_path.write_text(json.dumps(info, indent=1))
    uploader = Uploader(store, ckpt_root, cfg.keep_last, log)
    # TRL's num_tokens counts from 0 in each process, so per-step tokens are its deltas
    marks: dict[str, Any] = {"last_save": time.monotonic(), "t_log": time.monotonic(), "tokens": 0}

    def run_probe(step: int) -> None:
        row = {"step": step, "attempt": attempt, "usd_cum": round(clock.usd(), 4), **probe(model)}
        probe_log.write(row)
        log(
            f"probe step {step}: format {row['format']:.2f}, legal {row['legal']:.2f}, "
            f"<answer> {row['answer_tag']:.2f}, e.g. {row['examples'][0]!r}"
        )

    class Hooks(TrainerCallback):
        def on_train_begin(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            if state.global_step == 0:
                run_probe(0)
            marks["last_save"] = marks["t_log"] = time.monotonic()

        def on_log(self, args: Any, state: Any, control: Any, logs: Any = None, **kw: Any) -> None:
            if not logs or "loss" not in logs:
                return
            now = time.monotonic()
            step_s, marks["t_log"] = now - marks["t_log"], now
            tokens = logs.get("num_tokens")
            d_tok = tokens - marks["tokens"] if tokens is not None else None
            marks["tokens"] = tokens or 0
            free, total = torch.cuda.mem_get_info()
            row = {
                "step": state.global_step,
                "attempt": attempt,
                "loss": logs.get("loss"),
                "grad_norm": logs.get("grad_norm"),
                "lr": logs.get("learning_rate"),
                "entropy": logs.get("entropy"),
                "token_acc": logs.get("mean_token_accuracy"),
                "step_tokens": d_tok,
                "step_s": round(step_s, 3),
                "tok_s": round(d_tok / step_s, 1) if d_tok else None,
                "usd_step": round(clock.usd_for(step_s), 5),
                "usd_cum": round(clock.usd(), 4),
                "max_steps": state.max_steps,
                "mem_peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                "mem_used_gib": round((total - free) / 2**30, 2),
            }
            torch.cuda.reset_peak_memory_stats()
            steps_log.write(row)
            log(
                f"step {row['step']}/{state.max_steps}: loss {row['loss']:.4f}, acc {row['token_acc'] or 0:.3f}, "
                f"{row['step_s']:.1f} s, {row['tok_s'] or 0:.0f} tok/s, ${row['usd_cum']:.3f}"
            )

        def on_step_end(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            if state.global_step >= state.max_steps:
                return  # the final model is saved below
            due = time.monotonic() - marks["last_save"] >= cfg.save_minutes * 60
            if cfg.save_steps:
                due = due or state.global_step % cfg.save_steps == 0
            if due:
                uploader.wait()  # one copy at a time; it also frees the older local checkpoint
                control.should_save = True

        def on_save(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            marks["last_save"] = time.monotonic()
            uploader.start(Path(args.output_dir) / f"checkpoint-{state.global_step}")
            run_probe(state.global_step)
            push_out()

    trainer.add_callback(Hooks())
    signal.signal(signal.SIGTERM, on_sigterm)

    resume = None
    if (step := kc.latest(store, ckpt_root)) is not None:
        resume = str(kc.pull(store, ckpt_root, step, work / "resume"))
        log(f"resuming from checkpoint {step}")
    info["resumed_from"] = step
    trainer.train(resume_from_checkpoint=resume)
    uploader.wait()
    run_probe(trainer.state.global_step)

    final = work / "final" / "merged"
    save_final(trainer.model, path, final)
    for f in sorted(final.rglob("*")):
        if f.is_file():
            store.put(f, f"{root_uri}/final", f"merged/{f.relative_to(final).as_posix()}")
    dropped = kc.drop_all(store, ckpt_root)  # optimizer states aren't needed any more (§7)
    info |= {
        "ended": now_iso(),
        "final_step": trainer.state.global_step,
        "usd_job": round(clock.usd(), 4),
        "checkpoints_deleted": dropped,
    }
    info_path.write_text(json.dumps(info, indent=1))
    log(
        f"done: step {trainer.state.global_step}, final model in {root_uri}/final/merged, ${clock.usd():.3f}"
    )
    push_out()


if __name__ == "__main__":
    typer.run(main)
