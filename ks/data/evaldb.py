"""Seeded reservoir sample of the Lichess evaluation DB, streamed (DATA.md §1).

The file is 22 GB compressed, so it is never stored: we read the first
`max_lines` lines over HTTP and keep a uniform sample of `k` of them
(Algorithm R; a line is only JSON-parsed when it enters the reservoir).
"""

from __future__ import annotations

import io
import json
import random
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import polars as pl
import requests
import zstandard

URL = "https://database.lichess.org/lichess_db_eval.jsonl.zst"
SEED = 2026


def stream_lines(url: str = URL) -> Iterator[str]:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        reader = zstandard.ZstdDecompressor().stream_reader(r.raw)
        yield from io.TextIOWrapper(reader, encoding="utf-8")


def parse(line: str) -> dict[str, Any] | None:
    """The deepest evaluation's first PV, with the score turned to the side to move.

    The DB's `cp`/`mate` are from White's point of view (checked 2026-10-21:
    in Black-to-move positions the PVs are sorted by ascending cp). Returns
    None for entries without a usable PV.
    """
    d = json.loads(line)
    evals = [e for e in d.get("evals", []) if e.get("pvs")]
    if not evals:
        return None
    best = max(evals, key=lambda e: e.get("depth", 0))
    pv = best["pvs"][0]
    if not pv.get("line"):
        return None
    fields = d["fen"].split()
    sign = 1 if fields[1] == "w" else -1
    cp, mate = pv.get("cp"), pv.get("mate")
    return {
        "fen": " ".join(fields[:4]) + " 0 1",
        "cp": None if cp is None else sign * cp,
        "mate": None if mate is None else sign * mate,
        "line": pv["line"],
        "depth": best.get("depth", 0),
        "knodes": best.get("knodes", 0),
    }


def reservoir(
    lines: Iterable[str], k: int, max_lines: int, seed: int = SEED
) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """Uniform sample of k parsable lines among the first max_lines. Returns (line_no, row) and lines read."""
    rng = random.Random(seed)
    res: list[tuple[int, dict[str, Any]]] = []
    n = 0
    for n, line in enumerate(lines, start=1):
        if n > max_lines:
            n = max_lines
            break
        if len(res) < k:
            row = parse(line)
            if row is not None:
                res.append((n, row))
            continue
        j = rng.randrange(n)
        if j < k:
            row = parse(line)
            if row is not None:
                res[j] = (n, row)
    return sorted(res, key=lambda t: t[0]), n


def to_frame(sample: list[tuple[int, dict[str, Any]]]) -> pl.DataFrame:
    return pl.DataFrame(
        [{"line_no": n, **row} for n, row in sample],
        schema={
            "line_no": pl.Int64,
            "fen": pl.String,
            "cp": pl.Int64,
            "mate": pl.Int64,
            "line": pl.String,
            "depth": pl.Int64,
            "knodes": pl.Int64,
        },
    )


def build(out: Path, k: int, max_lines: int, seed: int = SEED) -> tuple[pl.DataFrame, int]:
    sample, read = reservoir(stream_lines(), k, max_lines, seed)
    df = to_frame(sample)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    return df, read
