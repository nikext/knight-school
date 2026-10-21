"""The answer parser (TRAINING.md §2): completion text -> one legal move, or why not.

The most-called code in the repo: every eval item and every RL rollout goes
through `parse`. Rules:

- The move is taken from the **last** `<answer>…</answer>` block.
- Tolerated inside the block: surrounding whitespace, `**`/backticks/quotes,
  a leading move number (`12.` / `12...`), a trailing period, annotation
  glyphs (`!`, `?`), a missing or extra `+`/`#`, and `0-0`/`0-0-0` for castling.
- After that the text must equal one of the position's legal moves in SAN
  (the prompt's list). Long algebraic (`e2e4`, `Ng1f3`) and null moves are
  *not* accepted, even though `board.parse_san` would take them: the prompt
  asks for a move from the list.

Format (for the 0.1 format reward and the format rate):

- `n_answers == 1` and no stray tags: exactly one `<answer>…</answer>` block
  and no other `<answer>` or `</answer>`;
- `think_ok`: exactly one `</think>`, at most one `<think>` (native thinking
  modes put the opening tag in the prompt), opened before it is closed, and
  the answer block after `</think>`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import chess

Status = Literal["ok", "no_answer", "unparseable", "illegal"]

_ANSWER = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
_MOVE_NUMBER = re.compile(r"^\d+\s*\.(\s*\.\.)?\s*")
_WRAP = "*`'\" \t\n"
# What a single SAN token can look like after normalisation (pieces, files, ranks, x, =, O-O).
_SAN_SHAPE = re.compile(r"^(O-O(-O)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=?[QRBN])?)$")


@dataclass(frozen=True)
class Parsed:
    status: Status
    move: chess.Move | None = None
    san: str | None = None  # canonical SAN of the move, as listed in the prompt
    raw: str | None = None  # the last answer block's text, unstripped
    n_answers: int = 0  # complete answer blocks
    stray_tags: bool = False  # an <answer> or </answer> outside a complete block
    think_ok: bool = False

    @property
    def legal(self) -> bool:
        return self.status == "ok"

    def well_formed(self, require_think: bool) -> bool:
        return self.n_answers == 1 and not self.stray_tags and (self.think_ok or not require_think)


def normalise(text: str) -> str:
    s = text.strip(_WRAP)
    s = _MOVE_NUMBER.sub("", s).strip(_WRAP)
    s = s.rstrip(".!? ").strip(_WRAP)
    s = s.rstrip("+#")
    if s in ("0-0", "0-0-0"):
        s = s.replace("0", "O")
    return s


def legal_map(board: chess.Board) -> dict[str, chess.Move]:
    """Legal moves keyed by SAN without check/mate suffix."""
    return {board.san(m).rstrip("+#"): m for m in board.legal_moves}


def _think_ok(text: str, answer_start: int) -> bool:
    opens, closes = text.count("<think>"), text.count("</think>")
    if closes != 1 or opens > 1:
        return False
    close = text.index("</think>")
    if opens == 1 and text.index("<think>") > close:
        return False
    return close < answer_start


def parse(text: str, board: chess.Board, legal: dict[str, chess.Move] | None = None) -> Parsed:
    """Parse a completion against `board`. Pass `legal` (from `legal_map`) to reuse it."""
    blocks = list(_ANSWER.finditer(text))
    n = len(blocks)
    stray = text.count("<answer>") != n or text.count("</answer>") != n
    if not blocks:
        return Parsed("no_answer", stray_tags=stray, think_ok=_think_ok(text, len(text)))
    fmt = {"n_answers": n, "stray_tags": stray, "think_ok": _think_ok(text, blocks[0].start())}
    raw = blocks[-1].group(1)
    s = normalise(raw)
    if not _SAN_SHAPE.match(s):
        return Parsed("unparseable", raw=raw, **fmt)
    move = (legal if legal is not None else legal_map(board)).get(s)
    if move is None:
        return Parsed("illegal", raw=raw, **fmt)
    return Parsed("ok", move, board.san(move), raw, **fmt)
