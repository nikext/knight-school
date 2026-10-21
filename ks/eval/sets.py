"""Eval sets (EVALS.md §1) as puzzles with their expanded solver positions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from ks.cloud.config import REPO
from ks.data.puzzles import N_BINS, RATING_LO, expand, rating_bin

SETS_DIR = REPO / "evals" / "sets"
PUZZLE_SETS = ("test2000", "test500", "dev500", "chessbench1k")
PROBE_SETS = ("probe500",)


@dataclass
class Puzzle:
    id: str
    rating: int
    bin: int
    positions: list[dict[str, Any]] = field(default_factory=list)


def _bin(rating: int) -> int:
    # chessbench ratings can fall below 400; they go in the lowest bin
    return rating_bin(max(rating, RATING_LO))


def load_puzzles(name: str, sets_dir: Path = SETS_DIR) -> list[Puzzle]:
    if name not in PUZZLE_SETS:
        raise ValueError(f"unknown puzzle set {name!r}; known: {PUZZLE_SETS}")
    csv = sets_dir / ("test2000.csv" if name == "test500" else f"{name}.csv")
    df = pl.read_csv(csv, schema_overrides={"PuzzleId": pl.String})
    if name == "test500":
        ids = (sets_dir / "test500.ids").read_text().split()
        df = df.filter(pl.col("PuzzleId").is_in(ids))
        assert df.height == len(ids), "test500.ids must be a subset of test2000"
    out = []
    for r in df.iter_rows(named=True):
        rating = int(r["Rating"])
        pos = expand(r["PuzzleId"], r["FEN"], r["Moves"], rating, with_legal=False)
        out.append(Puzzle(r["PuzzleId"], rating, _bin(rating), pos))
    return out


def spread(items: list[Any], limit: int | None) -> list[Any]:
    """`limit` items spread evenly over the list (the sets are sorted by rating bin)."""
    if limit is None or limit >= len(items):
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


def load_probe(sets_dir: Path = SETS_DIR) -> pl.DataFrame:
    return pl.read_csv(
        sets_dir / "probe500.csv", schema_overrides={"move": pl.String}
    ).with_columns(pl.col("move").fill_null(""))


__all__ = ["N_BINS", "PROBE_SETS", "PUZZLE_SETS", "Puzzle", "load_probe", "load_puzzles", "spread"]
