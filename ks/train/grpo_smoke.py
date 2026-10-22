"""M2 GRPO compatibility smoke (task M2 §6): a few TRL GRPO steps with LoRA and vLLM colocate.

This only checks that the stack runs for a model (load, generate in vLLM,
score with `ks.chess.rewards`, LoRA backward, weight sync back into vLLM).
Hyperparameters are M3's job; these are just small enough to fit an L4.

    python -m ks.train.grpo_smoke --model qwen3-1.7b --steps 5 --out /out/grpo-smoke
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Annotated, Any

import chess
import polars as pl
import typer

from ks.chess import prompt as kpr
from ks.chess import rewards as kr
from ks.eval import profile as prof

RL_TRAIN = "data/positions/rl_train.parquet"


def load_positions(path: str, n: int) -> list[dict[str, Any]]:
    if path.startswith("gs://"):
        from ks.cloud.gcs import download

        path = str(download(path, Path("/tmp/rl_train.parquet")))
    df = pl.read_parquet(path, columns=["fen", "solution_uci", "is_last", "legal_san", "wp"])
    return df.head(n).to_dicts()


def _text(completion: Any) -> str:
    # conversational datasets give [{"role": "assistant", "content": ...}]
    if isinstance(completion, list):
        return completion[-1]["content"]
    return completion


def make_rewards(require_think: bool):
    def _scores(completions, fen, solution_uci, is_last, legal_san, wp) -> list[kr.Reward]:
        out = []
        for c, f, s, last, legal, w in zip(
            completions, fen, solution_uci, is_last, legal_san, wp, strict=True
        ):
            t = kr.Target.from_record(
                {"fen": f, "solution_uci": s, "is_last": last, "legal_san": legal, "wp": w}
            )
            out.append(kr.score(_text(c), t, require_think))
        return out

    def dense(completions, fen, solution_uci, is_last, legal_san, wp, **_: Any) -> list[float]:
        return [
            r.dense or 0.0 for r in _scores(completions, fen, solution_uci, is_last, legal_san, wp)
        ]

    def fmt(completions, fen, solution_uci, is_last, legal_san, wp, **_: Any) -> list[float]:
        return [r.format for r in _scores(completions, fen, solution_uci, is_last, legal_san, wp)]

    return [dense, fmt]


def main(
    model: Annotated[str, typer.Option(help="Profile name in configs/models/.")],
    steps: int = 5,
    positions: int = 64,
    data: str = RL_TRAIN,
    out: Path = Path("/out/grpo-smoke"),
    max_completion: int = 512,
    vllm_mem: float = 0.35,
    batch: int = 8,
    generations: int = 8,
) -> None:
    import torch  # type: ignore[import-not-found]
    from datasets import Dataset  # type: ignore[import-not-found]
    from peft import LoraConfig  # type: ignore[import-not-found]
    from trl import GRPOConfig, GRPOTrainer  # type: ignore[attr-defined]

    p = prof.load(model)
    assert p.hf_repo, "GRPO smoke needs an open model"
    rows = load_positions(data, positions)
    for r in rows:
        r["prompt"] = kpr.messages(chess.Board(r["fen"]), p.think, p.legal_list)
    ds = Dataset.from_list(rows)

    run_dir = out / p.name
    run_dir.mkdir(parents=True, exist_ok=True)
    args = GRPOConfig(
        output_dir=str(run_dir),
        max_steps=steps,
        learning_rate=1e-5,
        per_device_train_batch_size=batch,
        gradient_accumulation_steps=1,
        num_generations=generations,
        max_completion_length=max_completion,
        temperature=1.0,
        beta=1e-3,
        bf16=True,
        gradient_checkpointing=True,
        use_vllm=True,
        vllm_mode="colocate",
        vllm_gpu_memory_utilization=vllm_mem,
        vllm_max_model_length=p.max_model_len,
        chat_template_kwargs=p.chat_template_kwargs or None,
        logging_steps=1,
        log_completions=True,
        save_strategy="no",
        report_to="none",
        seed=2026,
        model_init_kwargs={"revision": p.revision, "dtype": torch.bfloat16},
    )
    lora = LoraConfig(r=32, lora_alpha=64, target_modules="all-linear", task_type="CAUSAL_LM")
    t0 = time.monotonic()
    trainer = GRPOTrainer(
        model=p.hf_repo,
        reward_funcs=make_rewards(p.require_think),  # type: ignore[arg-type]
        args=args,
        train_dataset=ds,
        peft_config=lora,
    )
    t_init = time.monotonic() - t0
    trainer.train()
    t_train = time.monotonic() - t0 - t_init
    summary = {
        "model": p.name,
        "hf_repo": p.hf_repo,
        "steps": steps,
        "init_seconds": round(t_init, 1),
        "train_seconds": round(t_train, 1),
        "seconds_per_step": round(t_train / steps, 1),
        "peak_gpu_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "log_history": trainer.state.log_history,
    }
    (run_dir / "smoke.json").write_text(json.dumps(summary, indent=1, default=str))
    typer.echo(json.dumps({k: v for k, v in summary.items() if k != "log_history"}))


if __name__ == "__main__":
    typer.run(main)
