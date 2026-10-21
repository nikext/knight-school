"""Lichess puzzles: filter (DATA.md §2), split by game (§3), expand to solver positions (§4).

Ordering is decided by sha256(seed:PuzzleId), not by a library RNG, so the
splits stay the same across polars and Python versions.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import chess
import polars as pl
import zstandard

from ks.chess import board as kb

SEED = 2026
RAW_ZST = Path("raw/lichess_db_puzzle.csv.zst")
RAW_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
COLUMNS = [
    "PuzzleId",
    "FEN",
    "Moves",
    "Rating",
    "RatingDeviation",
    "Popularity",
    "NbPlays",
    "Themes",
    "GameUrl",
    "OpeningTags",
    "DailyDate",
]

RATING_LO, RATING_HI, BIN_WIDTH = 400, 2800, 200
N_BINS = (RATING_HI - RATING_LO) // BIN_WIDTH  # 12
MAX_SOLVER_MOVES = 4


def rating_bin(rating: int) -> int:
    """0..11 for 400..2800; 2800 itself goes in the top bin."""
    return min((rating - RATING_LO) // BIN_WIDTH, N_BINS - 1)


def bin_quotas(total: int, n_bins: int = N_BINS) -> list[int]:
    """Split `total` as evenly as possible; the lower bins get the remainder (2000 -> 8x167, 4x166)."""
    base, extra = divmod(total, n_bins)
    return [base + (1 if b < extra else 0) for b in range(n_bins)]


def order_key(seed: int, puzzle_id: str) -> str:
    return hashlib.sha256(f"{seed}:{puzzle_id}".encode()).hexdigest()


def game_id(game_url: str) -> str:
    """`https://lichess.org/787zsVup/black#48` -> `787zsVup`."""
    return game_url.split("lichess.org/", 1)[1].split("/", 1)[0].split("#", 1)[0]


# --- loading and filtering ---------------------------------------------------


def decompress(zst: Path, out: Path) -> Path:
    if not out.exists() or out.stat().st_mtime < zst.stat().st_mtime:
        tmp = out.with_suffix(".tmp")
        with zst.open("rb") as src, tmp.open("wb") as dst:
            zstandard.ZstdDecompressor().copy_stream(src, dst)
        tmp.rename(out)
    return out


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        schema_overrides={"DailyDate": pl.Int64, "OpeningTags": pl.String, "PuzzleId": pl.String},
    ).select(COLUMNS)


def filter_puzzles(df: pl.DataFrame) -> tuple[pl.DataFrame, list[tuple[str, int]]]:
    """DATA.md §2, in order. Returns the kept rows and (step, rows left) counts for the data card."""
    steps: list[tuple[str, pl.Expr]] = [
        ("NbPlays >= 200", pl.col("NbPlays") >= 200),
        ("RatingDeviation <= 90", pl.col("RatingDeviation") <= 90),
        ("Popularity >= 50", pl.col("Popularity") >= 50),
        (
            f"{RATING_LO} <= Rating <= {RATING_HI}",
            pl.col("Rating").is_between(RATING_LO, RATING_HI),
        ),
        (
            f"<= {MAX_SOLVER_MOVES} solver moves",
            pl.col("Moves").str.split(" ").list.len() <= 2 * MAX_SOLVER_MOVES,
        ),
    ]
    counts = [("downloaded", df.height)]
    for name, expr in steps:
        df = df.filter(expr)
        counts.append((name, df.height))
    return df, counts


def with_split_columns(df: pl.DataFrame, seed: int = SEED) -> pl.DataFrame:
    """Add game id, rating bin and the seeded order key, sorted by the order key."""
    return df.with_columns(
        pl.col("GameUrl").map_elements(game_id, return_dtype=pl.String).alias("game_id"),
        pl.col("Rating").map_elements(rating_bin, return_dtype=pl.Int64).alias("rating_bin"),
        pl.col("PuzzleId")
        .map_elements(lambda p: order_key(seed, p), return_dtype=pl.String)
        .alias("order"),
    ).sort("order")


# --- splits ---------------------------------------------------------------------


def pick_eval_sets(
    df: pl.DataFrame, sizes: dict[str, int], n_bins: int = N_BINS
) -> tuple[dict[str, pl.DataFrame], set[str]]:
    """Stratified eval sets, one puzzle per game, no game in two sets.

    `df` must come from `with_split_columns` (sorted by order). Sets are filled
    in the order of `sizes`, bin by bin. Returns the sets and the used games.
    """
    quotas = {name: bin_quotas(n, n_bins) for name, n in sizes.items()}
    picked: dict[str, list[int]] = {name: [] for name in sizes}
    used_games: set[str] = set()
    bins = df["rating_bin"].to_list()
    games = df["game_id"].to_list()
    for b in range(n_bins):
        idx = (i for i, x in enumerate(bins) if x == b)
        for name in sizes:
            need = quotas[name][b]
            while need:
                i = next(idx)  # StopIteration means a bin is too thin: fail loudly
                if games[i] in used_games:
                    continue
                used_games.add(games[i])
                picked[name].append(i)
                need -= 1
    return {name: df[rows] for name, rows in picked.items()}, used_games


def stratified_subset(df: pl.DataFrame, total: int) -> pl.DataFrame:
    """The first puzzles of each bin in order-key order (test500 from test2000)."""
    quotas = bin_quotas(total)
    return pl.concat(
        df.filter(pl.col("rating_bin") == b).sort("order").head(q) for b, q in enumerate(quotas)
    )


# --- expansion -------------------------------------------------------------------


def expand(
    puzzle_id: str,
    fen: str,
    moves: str,
    rating: int = 0,
    themes: str = "",
    with_legal: bool = True,
) -> list[dict[str, Any]]:
    """Solver positions of one puzzle (DATA.md §4).

    `ply` is the index of the solver's move in `Moves` (1, 3, 5, 7): the first
    entry is the opponent's move that sets up the puzzle.
    """
    uci = moves.split()
    board = chess.Board(fen)
    board.push(chess.Move.from_uci(uci[0]))
    out: list[dict[str, Any]] = []
    for ply in range(1, len(uci), 2):
        move = chess.Move.from_uci(uci[ply])
        if move not in board.legal_moves:
            raise ValueError(f"{puzzle_id}: illegal solution move {uci[ply]} at ply {ply}")
        out.append(
            {
                "puzzle_id": puzzle_id,
                "ply": ply,
                "key": kb.key(board),
                "fen": board.fen(),
                "legal_san": kb.legal_san(board) if with_legal else [],
                "solution_san": board.san(move),
                "solution_uci": move.uci(),
                "is_last": ply == len(uci) - 1,
                "rating": rating,
                "themes": themes,
            }
        )
        board.push(move)
        if ply + 1 < len(uci):
            board.push(chess.Move.from_uci(uci[ply + 1]))
    return out


def line_keys(fen: str, moves: str) -> list[str]:
    """Keys of every position along a puzzle line: before the opponent's move, then after each move."""
    board = chess.Board(fen)
    keys = [kb.key(board)]
    for uci in moves.split():
        board.push(chess.Move.from_uci(uci))
        keys.append(kb.key(board))
    return keys


def expand_frame(df: pl.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in df.iter_rows(named=True):
        rows.extend(expand(r["PuzzleId"], r["FEN"], r["Moves"], r["Rating"], r["Themes"]))
    return rows


def take_positions(
    df: pl.DataFrame,
    target: int,
    blocked: set[str],
    blocked_games: set[str],
    n_bins: int = N_BINS,
) -> tuple[pl.DataFrame, list[dict[str, Any]], dict[str, int]]:
    """rl_train: puzzles taken bin by bin in order-key order until each bin has its share of positions.

    Positions whose key is blocklisted or already taken are dropped (the rest
    of the puzzle stays). Returns the puzzles used, their positions and counts.
    """
    quotas = bin_quotas(target, n_bins)
    used_rows: list[int] = []
    positions: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats = {"blocklist_hits_dropped": 0, "duplicates_dropped": 0}
    bins = df["rating_bin"].to_list()
    games = df["game_id"].to_list()
    for b, quota in enumerate(quotas):
        got = 0
        for i in (i for i, x in enumerate(bins) if x == b):
            if got >= quota:
                break
            if games[i] in blocked_games:
                continue
            r = df.row(i, named=True)
            used_rows.append(i)
            for p in expand(r["PuzzleId"], r["FEN"], r["Moves"], r["Rating"], r["Themes"]):
                if p["key"] in blocked:
                    stats["blocklist_hits_dropped"] += 1
                elif p["key"] in seen:
                    stats["duplicates_dropped"] += 1
                else:
                    seen.add(p["key"])
                    positions.append(p)
                    got += 1
        if got < quota:
            raise ValueError(f"bin {b}: only {got} of {quota} positions available")
    return df[used_rows], positions, stats


def games_of(df: pl.DataFrame) -> set[str]:
    return set(df["game_id"].to_list())


def without_games(df: pl.DataFrame, games: Iterable[str]) -> pl.DataFrame:
    return df.filter(~pl.col("game_id").is_in(list(games)))
