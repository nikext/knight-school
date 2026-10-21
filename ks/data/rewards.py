"""Stockfish MultiPV reward tables for rl_train (DATA.md §6, ADR-005).

Every legal move of every position gets a score at a fixed node count, with
Threads=1 and a cleared hash per position, so a table is reproducible. Work is
split in shards that are written atomically, so an interrupted run resumes
where it stopped.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import chess
import chess.engine
import polars as pl

from ks.chess import board as kb

THREADS = 1
HASH_MB = 64
MULTIPV_CAP = 256  # Stockfish 19's MultiPV max (checked 2026-10-21); positions have ≤ 218 moves
MISMATCH_WP = 0.15  # drop positions where the solution is this much worse than the engine's best
WORKERS = 18  # 20 threads on the laptop, 2 left for the desktop


def stockfish_path() -> str:
    return os.path.expanduser(os.environ.get("STOCKFISH", "~/.local/bin/stockfish"))


def open_engine() -> chess.engine.SimpleEngine:
    eng = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    eng.configure({"Threads": THREADS, "Hash": HASH_MB})
    return eng


def sf_version() -> str:
    eng = chess.engine.SimpleEngine.popen_uci(stockfish_path())
    try:
        return eng.id.get("name", "unknown")
    finally:
        eng.quit()


def analyse(eng: chess.engine.SimpleEngine, fen: str, nodes: int) -> dict[str, Any]:
    """Score every legal move from the side to move's point of view.

    Returns legal_san (frozen order) with aligned cp / mate / wp lists, and
    the engine's best move. Raises if Stockfish didn't report every move.
    """
    board = chess.Board(fen)
    n = board.legal_moves.count()
    infos = eng.analyse(
        board,
        chess.engine.Limit(nodes=nodes),
        multipv=min(n, MULTIPV_CAP),
        game=object(),  # a new game per position: ucinewgame clears the hash
    )
    scores: dict[str, chess.engine.Score] = {}
    best = ""
    for info in infos:
        pv, score = info.get("pv"), info.get("score")
        if pv and score is not None:
            san = board.san(pv[0])
            scores[san] = score.pov(board.turn)
            best = best or san  # infos come in multipv order, best first
    sans = kb.legal_san(board)
    missing = [s for s in sans if s not in scores]
    if missing:
        raise RuntimeError(f"{fen}: no score for {missing}")
    cps = [scores[s].score() for s in sans]
    mates = [scores[s].mate() for s in sans]
    return {
        "legal_san": sans,
        "cp": cps,
        "mate": mates,
        "wp": [kb.win_prob(c, m) for c, m in zip(cps, mates, strict=True)],
        "sf_best_san": best,
    }


# --- process pool ------------------------------------------------------------------

_ENGINE: chess.engine.SimpleEngine | None = None


def _init() -> None:
    global _ENGINE
    _ENGINE = open_engine()


def _analyse_one(args: tuple[str, int]) -> tuple[dict[str, Any], float]:
    assert _ENGINE is not None
    t = time.perf_counter()
    return analyse(_ENGINE, args[0], args[1]), time.perf_counter() - t


def _run_shard(args: tuple[Path, Path, int, str]) -> tuple[str, int, float]:
    src, dst, nodes, version = args
    assert _ENGINE is not None
    df = pl.read_parquet(src)
    t = time.perf_counter()
    rows = []
    for r in df.iter_rows(named=True):
        res = analyse(_ENGINE, r["fen"], nodes)
        rows.append({**r, **res, "nodes": nodes, "sf_version": version})
    tmp = dst.with_suffix(".tmp")
    pl.DataFrame(rows).write_parquet(tmp)
    tmp.rename(dst)
    return dst.name, len(rows), time.perf_counter() - t


def time_positions(fens: list[str], nodes: int, workers: int) -> tuple[list[dict[str, Any]], float]:
    """Analyse fens in parallel; returns results (in order) and wall seconds."""
    t = time.perf_counter()
    with get_context("spawn").Pool(workers, initializer=_init) as pool:
        out = pool.map(_analyse_one, [(f, nodes) for f in fens], chunksize=1)
    return [r for r, _ in out], time.perf_counter() - t


def run_shards(
    positions: pl.DataFrame,
    work_dir: Path,
    nodes: int,
    shard_size: int,
    workers: int,
    log: Callable[[str], None],
) -> list[Path]:
    """Resumable: shard inputs are (re)written only if missing, outputs skipped if present.

    Each shard's engine seconds go to `secs.json` beside the outputs, so the total
    cost survives a resumed or skipped run (see `shard_seconds`).
    """
    version = sf_version()
    inputs, outputs = work_dir / "in", work_dir / f"out-n{nodes}"
    inputs.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)
    jobs = []
    for s, start in enumerate(range(0, positions.height, shard_size)):
        src, dst = inputs / f"shard-{s:04d}.parquet", outputs / f"shard-{s:04d}.parquet"
        if not src.exists():
            positions.slice(start, shard_size).write_parquet(src)
        if not dst.exists():
            jobs.append((src, dst, nodes, version))
    n_shards = -(-positions.height // shard_size)
    log(f"rewards: {n_shards - len(jobs)}/{n_shards} shards done, {len(jobs)} to go")
    if jobs:
        t0, done = time.perf_counter(), 0
        with get_context("spawn").Pool(workers, initializer=_init) as pool:
            for name, rows, secs in pool.imap_unordered(_run_shard, jobs):
                done += 1
                _record_secs(outputs, name, secs)
                el = time.perf_counter() - t0
                eta = el / done * (len(jobs) - done)
                log(
                    f"rewards: {name} {rows} pos in {secs:.0f}s; {done}/{len(jobs)} "
                    f"elapsed {el / 60:.1f} min, eta {eta / 60:.1f} min"
                )
    return sorted(outputs.glob("shard-*.parquet"))


def _record_secs(outputs: Path, name: str, secs: float) -> None:
    path = outputs / "secs.json"
    table = json.loads(path.read_text()) if path.exists() else {}
    table[name] = round(secs, 1)
    path.write_text(json.dumps(table, indent=0, sort_keys=True))


def shard_seconds(outputs: Path) -> dict[str, float]:
    """Engine seconds per finished shard (one worker, one thread each)."""
    path = outputs / "secs.json"
    return json.loads(path.read_text()) if path.exists() else {}


# --- agreement and the mismatch filter ----------------------------------------------


def agreement(df: pl.DataFrame) -> pl.DataFrame:
    """Per position: the solution's wp and mate, the best wp, and whether the engine agrees."""

    def row(r: dict[str, Any]) -> dict[str, Any]:
        i = r["legal_san"].index(r["solution_san"])
        j = r["legal_san"].index(r["sf_best_san"])
        sol_mate, best_mate = r["mate"][i], r["mate"][j]
        return {
            "solution_wp": r["wp"][i],
            "best_wp": max(r["wp"]),
            "sf_agrees": r["sf_best_san"] == r["solution_san"],
            "both_mate": (sol_mate or 0) > 0 and (best_mate or 0) > 0,
        }

    cols = df.select("legal_san", "solution_san", "sf_best_san", "wp", "mate").to_dicts()
    return df.with_columns(pl.DataFrame([row(r) for r in cols]))


def mismatch_filter(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    keep = df.filter(pl.col("best_wp") - pl.col("solution_wp") <= MISMATCH_WP)
    return keep, df.height - keep.height
