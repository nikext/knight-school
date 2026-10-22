"""Rewards (TRAINING.md §3), shared by eval scoring and GRPO.

A `Target` is one solver position: its board, the solution, whether it is the
puzzle's last solver move, and (for rl_train positions) the M1 reward table,
i.e. the win probability of every legal move (DATA.md §6).

    total = task reward (`sparse`, `dense` or `dense_norm`, per run config) + `format`

Illegal or unparseable answers get task reward 0; the format reward may still
apply. Every component is returned so the trainer can log each one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import chess

from ks.chess import board as kb
from ks.chess import parse as kp

FORMAT_REWARD = 0.1
TaskReward = Literal["sparse", "dense", "dense_norm"]


@dataclass
class Target:
    board: chess.Board
    solution: chess.Move
    is_last: bool
    wp: dict[str, float] | None = None  # canonical SAN -> win probability for the side to move
    legal: dict[str, chess.Move] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.legal:
            self.legal = kp.legal_map(self.board)

    @classmethod
    def from_record(cls, r: Mapping[str, Any]) -> Target:
        """From an rl_train / expanded-puzzle row: fen, solution_uci, is_last, [legal_san, wp]."""
        board = chess.Board(r["fen"])
        wp = None
        if r.get("wp") is not None:
            wp = dict(zip(r["legal_san"], r["wp"], strict=True))
        return cls(board, chess.Move.from_uci(r["solution_uci"]), bool(r["is_last"]), wp)


@dataclass(frozen=True)
class Reward:
    parsed: kp.Parsed
    format: float
    sparse: float
    dense: float | None
    dense_norm: float | None

    def total(self, task: TaskReward) -> float:
        value = getattr(self, task)
        if value is None:
            raise ValueError(f"{task} reward needs a reward table")
        return value + self.format

    def components(self) -> dict[str, float]:
        out = {"format": self.format, "sparse": self.sparse, "legal": float(self.parsed.legal)}
        if self.dense is not None:
            out["dense"] = self.dense
        if self.dense_norm is not None:
            out["dense_norm"] = self.dense_norm
        return out


def _norm(value: float, values: Sequence[float]) -> float:
    lo, hi = min(values), max(values)
    return 1.0 if hi == lo else (value - lo) / (hi - lo)


def score(text: str, target: Target, require_think: bool = True) -> Reward:
    p = kp.parse(text, target.board, target.legal)
    fmt = FORMAT_REWARD if p.well_formed(require_think) else 0.0
    ok = p.move is not None and kb.solver_move_ok(
        target.board, p.move, target.solution, target.is_last
    )
    dense = dense_norm = None
    if target.wp is not None:
        if p.san is None:
            dense = dense_norm = 0.0
        else:
            dense = target.wp[p.san]
            dense_norm = _norm(dense, list(target.wp.values()))
    return Reward(p, fmt, float(ok), dense, dense_norm)
