"""Contamination filter (DATA.md §5): no eval position or eval game may reach training data.

Keys are `ks.chess.board.key` (EPD with the ep square only when an ep capture
is legal). The blocklist holds every position along every line of test2000,
dev500 and probe500. The games file holds the eval puzzles' Lichess game ids.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import chess
import polars as pl

from ks.chess import board as kb
from ks.data import puzzles

EPD_FILE = "blocklist.epd.txt"
GAMES_FILE = "blocklist.games.txt"


def puzzle_keys(df: pl.DataFrame) -> set[str]:
    """Every position on every puzzle line (FEN, Moves columns)."""
    keys: set[str] = set()
    for fen, moves in df.select("FEN", "Moves").iter_rows():
        keys.update(puzzles.line_keys(fen, moves))
    return keys


def probe_keys(df: pl.DataFrame) -> set[str]:
    """The probe positions, plus the position after the move for the move-effect items."""
    keys: set[str] = set()
    for fen, move in df.select("fen", "move").iter_rows():
        board = chess.Board(fen)
        keys.add(kb.key(board))
        if move:
            board.push_san(move)
            keys.add(kb.key(board))
    return keys


def write(sets_dir: Path, keys: Iterable[str], games: Iterable[str]) -> tuple[Path, Path]:
    epd, gm = sets_dir / EPD_FILE, sets_dir / GAMES_FILE
    epd.write_text("".join(f"{k}\n" for k in sorted(set(keys))))
    gm.write_text("".join(f"{g}\n" for g in sorted(set(games))))
    return epd, gm


@dataclass(frozen=True)
class Blocklist:
    keys: frozenset[str]
    games: frozenset[str]

    @classmethod
    def load(cls, sets_dir: Path) -> Blocklist:
        def lines(p: Path) -> frozenset[str]:
            return frozenset(x for x in p.read_text().splitlines() if x)

        return cls(lines(sets_dir / EPD_FILE), lines(sets_dir / GAMES_FILE))

    def hit(self, board: chess.Board) -> bool:
        return kb.key(board) in self.keys

    def hits_fens(self, fens: Iterable[str]) -> int:
        """How many of these FENs are blocklisted (the post-hoc check behind `contamination_hits`)."""
        return sum(kb.key(kb.board_from_fen(f)) in self.keys for f in fens)
