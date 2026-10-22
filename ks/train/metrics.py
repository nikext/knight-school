"""Per-step training metrics (TRAINING.md §4), written as JSONL next to TensorBoard.

`<out>/metrics/attempt-<n>.jsonl` holds one row per optimizer step, and
`dev-attempt-<n>.jsonl` one row per dev eval. A preemption retry pulls the
earlier attempts' files and carries on with the dollar count, so the curves
are "dev solve rate vs dollars spent" across attempts. A step redone after a
resume is paid for again and appears again; plots keep the last row per step.

Dollars here are the job's wall time times the machine's spot price. The VM's
boot and image pull aren't in them, so the ledger is still the total.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

# TRL log key -> our column name
KEYS = {
    "loss": "loss",
    "grad_norm": "grad_norm",
    "learning_rate": "lr",
    "reward": "reward",
    "reward_std": "reward_std",
    "frac_reward_zero_std": "frac_zero_std",
    "kl": "kl",
    "entropy": "entropy",
    "completions/mean_length": "len_mean",
    "completions/p95_length": "len_p95",
    "completions/max_length": "len_max",
    "completions/clipped_ratio": "clipped",
    "completions/tokens": "completion_tokens",
    "reasoning/prose_frac": "prose_frac",
    "reasoning/prose_chars_mean": "prose_chars",
    "step_time": "step_s",
}


class CostClock:
    """Dollars since this process started, plus what earlier attempts spent."""

    def __init__(self, usd_per_hour: float, base_usd: float = 0.0) -> None:
        self.rate = usd_per_hour / 3600
        self.base = base_usd
        self.t0 = time.monotonic()

    def usd(self) -> float:
        return self.base + (time.monotonic() - self.t0) * self.rate

    def usd_for(self, seconds: float) -> float:
        return seconds * self.rate


def step_row(
    logs: dict[str, Any],
    *,
    step: int,
    attempt: int,
    clock: CostClock,
    gen_seconds: float,
    prompt_tokens: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {"step": step, "attempt": attempt}
    for k, v in logs.items():
        if k in KEYS:
            row[KEYS[k]] = v
        elif k.startswith("rewards/") and k.endswith(("/mean", "/std")):
            _, name, stat = k.split("/")
            row[f"{name}_{stat}"] = v
    if "format_mean" in row:
        row["format_rate"] = row["format_mean"] / 0.1
    if "legal_mean" in row:
        row["legal_rate"] = row["legal_mean"]
    step_s = float(row.get("step_s") or 0.0)
    comp = float(row.get("completion_tokens") or 0.0)
    train_s = max(step_s - gen_seconds, 1e-9)
    row["gen_s"] = round(gen_seconds, 3)
    row["gen_tok_s"] = round(comp / gen_seconds, 1) if gen_seconds > 0 else None
    row["train_tok_s"] = round((comp + prompt_tokens) / train_s, 1) if step_s > 0 else None
    row["usd_step"] = round(clock.usd_for(step_s), 5)
    row["usd_cum"] = round(clock.usd(), 4)
    return row


class Jsonl:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def write(self, rows: list[dict[str, Any]] | dict[str, Any]) -> None:
        rows = [rows] if isinstance(rows, dict) else rows
        with self.path.open("a") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")


def read_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for p in paths:
        if p.exists():
            rows += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return rows


def spent_before(metrics_dir: Path, attempt: int) -> float:
    """The highest dollar count any earlier attempt reached (0 for the first)."""
    paths = [
        metrics_dir / f"{kind}attempt-{a}.jsonl" for a in range(1, attempt) for kind in ("", "dev-")
    ]
    return max((float(r.get("usd_cum") or 0) for r in read_rows(paths)), default=0.0)


def last_per_step(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows sorted by step, keeping the latest attempt's row where a resume repeated a step."""
    by: dict[int, dict[str, Any]] = {}
    for r in rows:
        s = int(r["step"])
        if s not in by or r.get("attempt", 0) >= by[s].get("attempt", 0):
            by[s] = r
    return [by[s] for s in sorted(by)]
