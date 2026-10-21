"""Position conventions shared by data, eval and training. Frozen in M1 (DATA.md §4, §5).

Changing anything here changes prompts, rewards and the contamination keys, so
every dataset would have to be rebuilt. Don't.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import chess

# Lichess win-probability constant (lila: WinPercent.scala).
_WP_K = 0.00368208
_CP_CLAMP = 1000


def key(board: chess.Board) -> str:
    """Contamination key: placement, side to move, castling, ep only if an ep capture is legal."""
    return board.epd(en_passant="legal")


def sort_san(sans: Iterable[str]) -> list[str]:
    """The one legal-move ordering: plain code-point order of the SAN strings.

    Upper case sorts before lower case, so piece moves (B, K, N, O-O, Q, R)
    come first and pawn moves last, e.g. `Bb5, Nf3, O-O, Qe2, a3, exd5`.
    """
    return sorted(sans)


def legal_san(board: chess.Board) -> list[str]:
    """All legal moves of the side to move as SAN, in the frozen order."""
    return sort_san(board.san(m) for m in board.legal_moves)


def board_from_fen(fen: str) -> chess.Board:
    """A standard board from a 4- or 6-field FEN (the eval DB omits the move counters)."""
    if len(fen.split()) == 4:
        fen += " 0 1"
    return chess.Board(fen)


def uci960_to_moves(board: chess.Board, line: Iterable[str]) -> list[chess.Move]:
    """Parse a UCI_Chess960 PV (castling as king-takes-rook, `e1h1`) against a standard board.

    Returns standard-notation moves (`e1g1` for O-O) that are legal on `board`
    in sequence. Stops at the first move that isn't legal.
    """
    b960 = chess.Board(board.fen(), chess960=True)
    std = board.copy(stack=False)
    out: list[chess.Move] = []
    for uci in line:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in b960.legal_moves:
            break
        san = b960.san(move)
        std_move = std.parse_san(san)
        out.append(std_move)
        b960.push(move)
        std.push(std_move)
    return out


def pv_to_san(board: chess.Board, line: Iterable[str]) -> list[str]:
    """A UCI_Chess960 PV as SAN, from `board`'s position."""
    b = board.copy(stack=False)
    sans: list[str] = []
    for move in uci960_to_moves(board, line):
        sans.append(b.san(move))
        b.push(move)
    return sans


def win_prob(cp: int | None = None, mate: int | None = None) -> float:
    """Lichess win probability for the side the score belongs to.

    `cp` is clamped to ±1000 like lila does. `mate > 0` means that side mates
    (wp 1), `mate < 0` that it gets mated (wp 0). `mate == 0` is a position
    that is already mate for the side to move, so 0.
    """
    if mate is not None:
        return 1.0 if mate > 0 else 0.0
    if cp is None:
        raise ValueError("need cp or mate")
    c = max(-_CP_CLAMP, min(_CP_CLAMP, cp))
    return 0.5 + 0.5 * (2 / (1 + math.exp(-_WP_K * c)) - 1)


def solver_move_ok(
    board: chess.Board, move: chess.Move, solution: chess.Move, is_last: bool
) -> bool:
    """Lichess's rule: the solution move, or on the puzzle's last move any move that mates."""
    if move == solution:
        return True
    if not is_last or move not in board.legal_moves:
        return False
    after = board.copy(stack=False)
    after.push(move)
    return after.is_checkmate()
