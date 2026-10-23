"""Merging a run's attempts, and a run finished under a new id, into results/train/<id>/."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from ks.train import metrics as km
from ks.train import report as tr


def _attempt(
    root: Path, attempt: int, steps: list[tuple[int, float]], dev: list[tuple[int, float]]
):
    out = root / str(attempt) / "out"
    km.Jsonl(out / "metrics" / f"attempt-{attempt}.jsonl").write(
        [{"step": s, "attempt": attempt, "usd_cum": u} for s, u in steps]
    )
    km.Jsonl(out / "metrics" / f"dev-attempt-{attempt}.jsonl").write(
        [{"step": s, "attempt": attempt, "usd_cum": u, "solve": 0.2} for s, u in dev]
    )
    (out / "run").mkdir(parents=True)
    (out / "run" / f"attempt-{attempt}.json").write_text(json.dumps({"attempt": attempt}))
    return out


def _rows(p: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(p.open()))


def test_a_continuation_counts_as_later_attempts(tmp_path: Path):
    first = [
        _attempt(tmp_path / "a", 1, [(1, 1.0), (2, 2.0)], [(0, 0.5)]),
        _attempt(tmp_path / "a", 2, [(2, 3.0), (3, 4.0), (4, 5.0)], [(4, 5.1)]),
    ]
    # the new id resumed from step 3's checkpoint; its clock started at $0
    then = [_attempt(tmp_path / "b", 1, [(4, 1.0), (5, 2.0)], [(5, 2.1)])]
    dest = tmp_path / "dest"
    counts = tr.collect([first, then], dest)

    steps = _rows(dest / "steps.csv")
    assert counts["steps"] == 5 and [r["step"] for r in steps] == ["1", "2", "3", "4", "5"]
    assert [r["attempt"] for r in steps] == ["1", "2", "2", "3", "3"]
    assert [float(r["usd_cum"]) for r in steps] == pytest.approx([1.0, 3.0, 4.0, 6.1, 7.1])
    dev = _rows(dest / "dev.csv")
    assert [r["step"] for r in dev] == ["0", "4", "5"]
    assert [float(r["usd_cum"]) for r in dev] == pytest.approx([0.5, 5.1, 7.2])
    assert sorted(p.name for p in dest.glob("run-*.json")) == [
        "run-attempt-1.json",
        "run-attempt-2.json",
        "run-attempt-3.json",
    ]


def test_a_single_run_is_unchanged(tmp_path: Path):
    outs = [_attempt(tmp_path, 1, [(1, 1.0), (2, 2.0)], [(0, 0.5)])]
    tr.collect([outs], tmp_path / "dest")
    steps = _rows(tmp_path / "dest" / "steps.csv")
    assert [(r["attempt"], float(r["usd_cum"])) for r in steps] == [("1", 1.0), ("1", 2.0)]
