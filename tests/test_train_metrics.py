"""Per-step metric rows, dollar counts across attempts, last row per step."""

from __future__ import annotations

from pathlib import Path

import pytest

from ks.train import metrics as km


def test_step_row_renames_and_derives():
    clock = km.CostClock(usd_per_hour=3.6)  # $0.001 per second
    logs = {
        "rewards/dense/mean": 0.3,
        "rewards/format/mean": 0.08,
        "rewards/legal/mean": 0.95,
        "completions/tokens": 4000.0,
        "completions/mean_length": 7.8,
        "step_time": 20.0,
        "kl": 0.001,
    }
    row = km.step_row(logs, step=3, attempt=1, clock=clock, gen_seconds=5.0, prompt_tokens=110_000)
    assert row["dense_mean"] == 0.3 and row["legal_rate"] == 0.95
    assert row["format_rate"] == pytest.approx(0.8)
    assert row["gen_tok_s"] == 800.0
    assert row["train_tok_s"] == pytest.approx((4000 + 110_000) / 15.0, rel=1e-3)
    assert row["usd_step"] == pytest.approx(0.02)
    assert row["len_mean"] == 7.8 and row["kl"] == 0.001


def test_dollars_carry_over_from_earlier_attempts(tmp_path: Path):
    km.Jsonl(tmp_path / "attempt-1.jsonl").write(
        [{"step": 1, "usd_cum": 0.5}, {"step": 2, "usd_cum": 1.25}]
    )
    km.Jsonl(tmp_path / "dev-attempt-1.jsonl").write({"step": 0, "usd_cum": 1.3})
    assert km.spent_before(tmp_path, 1) == 0.0
    assert km.spent_before(tmp_path, 2) == 1.3
    assert km.CostClock(3600, base_usd=1.3).usd() >= 1.3


def test_last_per_step_prefers_the_latest_attempt():
    rows = [
        {"step": 1, "attempt": 1, "v": "a"},
        {"step": 2, "attempt": 1, "v": "a"},
        {"step": 2, "attempt": 2, "v": "b"},
        {"step": 3, "attempt": 2, "v": "b"},
    ]
    assert [r["v"] for r in km.last_per_step(rows)] == ["a", "b", "b"]
