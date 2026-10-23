"""GRPO on rl_train (task M3 §2, TRAINING.md §4, §7): TRL GRPOTrainer, vLLM colocate, LoRA.

    python -m ks.train.grpo --config configs/train/grpo_dense.yaml [--set steps=20 ...]

One process does one attempt:
  1. resume from the newest complete checkpoint under the run's checkpoint root, if any;
  2. train, with a greedy dev eval on the colocated vLLM engine every `eval_every` steps,
     per-step metrics with $/step, and each checkpoint copied off the VM as it is saved;
  3. save the final adapter and the merged model (what `ks eval --ckpt` loads).
On SIGTERM (a preemption) it flushes metrics, leaves a marker in <out> and exits 143;
the next attempt resumes. Inside a ks VM the paths come from KS_GCS_PREFIX; on the
laptop everything is local (`--root`), which runs the same checkpoint code.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import chess
import polars as pl
import typer

from ks.chess import prompt as kpr
from ks.data.manifest import git_sha
from ks.eval import profile as prof
from ks.train import ckpt as kc
from ks.train import metrics as km
from ks.train.config import GrpoConfig, load
from ks.train.rewards import RewardFns
from ks.train.trim import install_sorted_batches, trimmed

COLUMNS = ["fen", "solution_uci", "is_last", "legal_san", "wp"]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_root(root: str | None, out: Path) -> str:
    """gs://BUCKET/runs/<id> inside a ks VM, else the --root dir (default: <out>/remote)."""
    if root:
        return root.rstrip("/")
    prefix = os.environ.get("KS_GCS_PREFIX")
    if prefix:
        return prefix.split("/attempts/")[0]
    return str(out / "remote")


def fetch(uri: str, dest: Path) -> Path:
    if not uri.startswith("gs://"):
        return Path(uri)
    from ks.cloud import gcs

    if uri.endswith(".parquet"):
        return gcs.download(uri, dest / Path(uri).name)
    return gcs.download_prefix(uri, dest)


def load_rows(cfg: GrpoConfig, p: prof.Profile, work: Path) -> list[dict[str, Any]]:
    """rl_train rows with their prompt; refuses any position on the eval blocklist (DATA.md §5)."""
    from ks.data.blocklist import Blocklist
    from ks.eval.sets import SETS_DIR

    df = pl.read_parquet(fetch(cfg.data, work / "data"), columns=COLUMNS)
    if cfg.positions:
        df = df.head(cfg.positions)
    hits = Blocklist.load(SETS_DIR).hits_fens(df["fen"].to_list())
    if hits:
        raise SystemExit(f"{hits} training positions are on the eval blocklist; refusing to train")
    rows = df.to_dicts()
    for r in rows:
        r["prompt"] = kpr.messages(chess.Board(r["fen"]), p.think, cfg.legal_list)
    return rows


def model_dir(cfg: GrpoConfig, p: prof.Profile, work: Path) -> str:
    """A local snapshot at the pinned revision, so trainer, vLLM and tokenizer load the same files."""
    if cfg.init_ckpt:
        return str(fetch(cfg.init_ckpt, work / "init"))
    from huggingface_hub import snapshot_download  # type: ignore[import-not-found]

    assert p.hf_repo, f"{p.name} is not an open model"
    return snapshot_download(p.hf_repo, revision=p.revision)


def lora_targets(model: Any) -> list[str]:
    """Every linear layer of the language model: not the vision tower, not the LM head (ADR-018)."""
    import torch  # type: ignore[import-not-found]

    names = [
        n
        for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "visual" not in n and not n.endswith("lm_head")
    ]
    if not names:
        raise RuntimeError("no linear layers found for LoRA")
    return names


def engine_kwargs(p: prof.Profile) -> None:
    """Give TRL's colocated vLLM engine the profile's language_model_only and enforce_eager.

    TRL 1.16 builds the engine itself and passes neither. Without language_model_only, vLLM
    loads the VLM's vision tower and reserves memory for dummy image inputs (it left no KV
    cache for Qwen3.5-0.8B on the laptop's 6 GB). The trainer still syncs every language-model
    weight into the engine.
    """
    from functools import partial

    from trl.generation import vllm_generation  # type: ignore[import-not-found]

    extra = {}
    if p.language_model_only:
        extra["language_model_only"] = True
    if p.enforce_eager:
        extra["enforce_eager"] = True
    if extra:
        vllm_generation.LLM = partial(vllm_generation.LLM, **extra)  # type: ignore[assignment]


def versions() -> dict[str, str]:
    import importlib.metadata as md

    out = {"python": platform.python_version()}
    for pkg in ("torch", "vllm", "trl", "peft", "transformers", "accelerate", "fla-core"):
        with contextlib.suppress(md.PackageNotFoundError):
            out[pkg] = md.version(pkg)
    return out


def run_info(cfg: GrpoConfig, overrides: dict[str, Any], attempt: int) -> dict[str, Any]:
    from ks.cloud.config import REPO

    manifest = REPO / "manifests" / "rl_train.json"
    data = json.loads(manifest.read_text()) if manifest.exists() else {}
    return {
        "run_id": os.environ.get("KS_RUN_ID", cfg.name),
        "attempt": attempt,
        "git_sha": git_sha(),
        "image": os.environ.get("KS_IMAGE"),
        "machine": os.environ.get("KS_MACHINE"),
        "zone": os.environ.get("KS_ZONE"),
        "price_per_hour": float(os.environ.get("KS_PRICE_PER_HOUR", "0") or 0),
        "config": cfg.model_dump(),
        "config_hash": cfg.hash(),
        "overrides": overrides,
        "prompt_hash": kpr.prompt_hash("tags", cfg.legal_list),
        "data": {"rl_train_sha256": data.get("sha256"), "rows": data.get("rows")},
        "seed": cfg.seed,
        "versions": versions(),
        "started": now_iso(),
    }


class EngineBackend:
    """The eval harness's Backend on the trainer's colocated vLLM engine (greedy)."""

    def __init__(self, vllm_generation: Any, p: prof.Profile) -> None:
        self.vg = vllm_generation
        self.p = p
        self.cost_usd = 0.0

    def generate(self, reqs: list[Any], n: int = 1) -> list[list[Any]]:
        from vllm import SamplingParams  # type: ignore[import-not-found]

        from ks.eval.backends import Completion

        sp = SamplingParams(n=1, temperature=0.0, max_tokens=self.p.max_tokens, seed=self.p.seed)
        outs = self.vg.llm.chat(
            [r.messages for r in reqs],
            sp,
            use_tqdm=False,
            chat_template_kwargs=self.p.chat_template_kwargs or None,
        )
        return [
            [
                Completion(
                    c.text,
                    len(o.prompt_token_ids or []),
                    len(c.token_ids),
                    c.finish_reason or "stop",
                )
                for c in o.outputs
            ]
            for o in outs
        ]

    def close(self) -> None:
        pass


def main(
    config: Annotated[str, typer.Option(help="configs/train/<arm>.yaml")],
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
    from datasets import Dataset  # type: ignore[import-not-found]
    from peft import LoraConfig  # type: ignore[import-not-found]
    from transformers import AutoConfig, TrainerCallback  # type: ignore[import-not-found]
    from trl import GRPOConfig, GRPOTrainer  # type: ignore[attr-defined]

    from ks.eval import harness, report, sets

    cfg, overrides = load(config, set_)
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
    log = lambda s: typer.echo(f"[grpo {cfg.name}] {now_iso()} {s}", err=True)  # noqa: E731

    clock = km.CostClock(price, km.spent_before(out / "metrics", attempt))
    steps_log = km.Jsonl(out / "metrics" / f"attempt-{attempt}.jsonl")
    dev_log = km.Jsonl(out / "metrics" / f"dev-attempt-{attempt}.jsonl")
    samples = km.Jsonl(out / "samples" / f"attempt-{attempt}.jsonl")
    info = run_info(cfg, overrides, attempt)
    info_path = out / "run" / f"attempt-{attempt}.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    info_path.write_text(json.dumps(info, indent=1))

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
    engine_kwargs(p)
    eval_profile = p.model_copy(
        update={"max_tokens": cfg.max_completion, "legal_list": cfg.legal_list}
    )
    rows = load_rows(cfg, p, work)
    ds = Dataset.from_list(rows)
    path = model_dir(cfg, p, work)
    log(f"{len(rows)} positions, model {path}, config {cfg.hash()}, attempt {attempt}")

    archs = AutoConfig.from_pretrained(path).architectures or ["AutoModelForCausalLM"]
    arch = getattr(transformers, archs[0])  # as TRL does: Qwen3.5 loads as the full VLM class
    model = arch.from_pretrained(path, dtype=torch.bfloat16)
    lora = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        lora_dropout=cfg.lora_dropout,
        target_modules=lora_targets(model),
        task_type="CAUSAL_LM",
    )
    fns = RewardFns(cfg.task_reward, p.require_think, samples.write, cfg.samples_per_step)
    reward_funcs, weights = fns.funcs()
    args = GRPOConfig(
        output_dir=str(work / "trainer"),
        max_steps=cfg.steps,
        learning_rate=cfg.learning_rate,
        lr_scheduler_type=cfg.lr_scheduler,
        warmup_steps=cfg.warmup_steps,
        weight_decay=cfg.weight_decay,
        max_grad_norm=cfg.max_grad_norm,
        per_device_train_batch_size=cfg.micro_batch,
        gradient_accumulation_steps=cfg.grad_accum,
        num_generations=cfg.generations,
        max_completion_length=cfg.max_completion,
        temperature=cfg.temperature,
        beta=cfg.beta,
        loss_type=cfg.loss_type,
        mask_truncated_completions=cfg.mask_truncated,
        entropy_coef=cfg.entropy_coef,
        use_adaptive_entropy=cfg.entropy_adaptive,
        entropy_target=cfg.entropy_target,
        entropy_coef_delta=cfg.entropy_coef_delta,
        reward_weights=weights,
        bf16=True,
        gradient_checkpointing=cfg.gradient_checkpointing,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        use_vllm=True,
        vllm_mode="colocate",
        vllm_gpu_memory_utilization=cfg.vllm_mem,
        vllm_max_model_length=p.max_model_len,
        vllm_enable_sleep_mode=cfg.vllm_sleep,
        chat_template_kwargs=p.chat_template_kwargs or None,
        logging_steps=1,
        report_to=["tensorboard"],
        save_strategy="steps",
        save_steps=cfg.save_every,
        save_total_limit=cfg.keep_last,
        seed=cfg.seed,
    )
    t0 = time.monotonic()
    install_sorted_batches()  # micro-batches by completion length (exact under dapo, ADR-019)
    trainer: Any = trimmed(GRPOTrainer)(  # drops right padding per chunk (ADR-019)
        model=model,
        reward_funcs=reward_funcs,  # type: ignore[arg-type]
        args=args,
        train_dataset=ds,
        peft_config=lora,
    )
    trainable = sum(x.numel() for x in trainer.model.parameters() if x.requires_grad)
    info |= {"init_seconds": round(time.monotonic() - t0, 1), "lora_params": trainable}
    info_path.write_text(json.dumps(info, indent=1))
    log(f"trainer ready in {info['init_seconds']} s, {trainable:,} LoRA parameters")

    # time each rollout batch: TRL only reports its profiling timings to wandb/mlflow
    vg = trainer.vllm_generation
    gen = {"s": 0.0}
    _generate = vg.generate

    def timed_generate(*a: Any, **kw: Any) -> Any:
        t = time.monotonic()
        try:
            return _generate(*a, **kw)
        finally:
            gen["s"] += time.monotonic() - t

    vg.generate = timed_generate
    tok: Any = trainer.processing_class
    tok = getattr(tok, "tokenizer", tok)
    sample = rows[: min(256, len(rows))]
    texts = [
        tok.apply_chat_template(
            r["prompt"],
            add_generation_prompt=True,
            tokenize=False,
            **(p.chat_template_kwargs or {}),
        )
        for r in sample
    ]
    prompt_len = sum(len(ids) for ids in tok(texts, add_special_tokens=False)["input_ids"]) / len(
        sample
    )
    info["prompt_tokens_mean"] = round(prompt_len, 1)
    info_path.write_text(json.dumps(info, indent=1))
    puzzles = sets.spread(sets.load_puzzles(cfg.eval_set), cfg.eval_limit) if cfg.eval_every else []

    def dev_eval(step: int) -> None:
        t = time.monotonic()
        vg.sync_weights()
        trainer._last_loaded_step = step  # the engine now has this step's weights
        name = f"{cfg.name}-step{step:04d}"
        run = harness.EvalRun(
            eval_profile, cfg.eval_set, puzzles, run_name=name, checkpoint=f"step {step}"
        )
        res = harness.run(run, EngineBackend(vg, eval_profile))
        report.write(res, out / "eval")
        s = res["summary"]
        row = {
            "step": step,
            "attempt": attempt,
            "usd_cum": round(clock.usd(), 4),
            "seconds": round(time.monotonic() - t, 1),
            "solve": s["solve"]["value"],
            "solve_lo": s["solve"]["lo"],
            "solve_hi": s["solve"]["hi"],
            "move_acc": s["move_acc"]["value"],
            "legal": s["legal"]["value"],
            "format": s["format"]["value"],
            "tokens_out_mean": s["tokens_out_mean"],
            "tokens_out_p95": s["tokens_out_p95"],
            "truncated": s["truncated"],
        }
        dev_log.write(row)
        log(
            f"dev {cfg.eval_set} step {step}: solve {row['solve']:.3f}, legal {row['legal']:.3f}, {row['seconds']} s"
        )
        push_out()

    class Hooks(TrainerCallback):
        def on_train_begin(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            if cfg.eval_every and cfg.eval_at_start and state.global_step == 0:
                dev_eval(0)

        def on_log(self, args: Any, state: Any, control: Any, logs: Any = None, **kw: Any) -> None:
            if not logs or "step_time" not in logs:
                return
            row = km.step_row(
                logs,
                step=state.global_step,
                attempt=attempt,
                clock=clock,
                gen_seconds=gen["s"],
                prompt_tokens=int(prompt_len * cfg.completions_per_step),
            )
            gen["s"] = 0.0
            # memory: torch's peak in this step (trainer + the colocated engine, one process)
            # and the whole device in use now, so micro_batch and vllm_mem can be sized
            free, total = torch.cuda.mem_get_info()
            row["mem_peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
            row["mem_used_gib"] = round((total - free) / 2**30, 2)
            torch.cuda.reset_peak_memory_stats()
            if trainer.total_columns:
                row["trim_frac"] = round(trainer.trimmed_columns / trainer.total_columns, 3)
            trainer.trimmed_columns = trainer.total_columns = 0
            steps_log.write(row)
            log(
                f"step {row['step']}: reward {row.get('reward', 0):.3f}, legal {row.get('legal_rate', 0):.3f}, "
                f"len {row.get('len_mean', 0):.0f}/{row.get('len_p95', 0):.0f}, {row['step_s']:.1f} s, ${row['usd_cum']:.3f}"
            )

        def on_step_end(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            if cfg.eval_every and state.global_step % cfg.eval_every == 0:
                dev_eval(state.global_step)

        def on_save(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
            local = Path(args.output_dir) / f"checkpoint-{state.global_step}"
            try:
                n = kc.push(store, local, ckpt_root, cfg.keep_last)
            except (
                Exception
            ) as e:  # the next checkpoint tries again; a retry resumes from an older one
                log(
                    f"checkpoint {state.global_step}: copy to {ckpt_root} FAILED ({e}); training on"
                )
            else:
                log(f"checkpoint {state.global_step}: {n} files to {ckpt_root}")
            push_out()

    trainer.add_callback(Hooks())
    signal.signal(signal.SIGTERM, on_sigterm)  # again: vLLM's engine init may install its own

    resume = None
    if (step := kc.latest(store, ckpt_root)) is not None:
        resume = str(kc.pull(store, ckpt_root, step, work / "resume"))
        log(f"resuming from checkpoint {step}")
    info["resumed_from"] = step
    if resume is not None and step is not None and step >= cfg.steps:
        # Preempted between the last checkpoint and the final save. trainer.train() would run
        # one step past max_steps here (seen in the laptop smoke), so load the adapter and skip.
        from peft import set_peft_model_state_dict  # type: ignore[import-not-found]
        from safetensors.torch import load_file  # type: ignore[import-not-found]

        set_peft_model_state_dict(
            trainer.model, load_file(str(Path(resume) / "adapter_model.safetensors"))
        )
        trainer.state.global_step = step
        log(f"checkpoint {step} is the last step; saving the final model without training")
    else:
        trainer.train(resume_from_checkpoint=resume)

    final = work / "final"
    trainer.save_model(str(final / "adapter"))
    merged = trainer.model.merge_and_unload()  # type: ignore[operator]
    merged.save_pretrained(str(final / "merged"))
    trainer.processing_class.save_pretrained(str(final / "merged"))
    for part in ("adapter", "merged"):
        for f in sorted((final / part).rglob("*")):
            if f.is_file():
                store.put(
                    f, f"{root_uri}/final", f"{part}/{f.relative_to(final / part).as_posix()}"
                )
    info |= {
        "ended": now_iso(),
        "final_step": trainer.state.global_step,
        "usd_job": round(clock.usd(), 4),
    }
    info_path.write_text(json.dumps(info, indent=1))
    log(
        f"done: step {trainer.state.global_step}, final model in {root_uri}/final, ${clock.usd():.3f}"
    )
    push_out()


if __name__ == "__main__":
    typer.run(main)
