"""The puzzle prompt shared by eval, RL and the probes (TRAINING.md §2). Frozen in M2.

The user turn reuses the primer's framing (`ks.data.primer.user_prompt`), so
the primer's T5 examples and the RL prompt only differ in the last line.

Two variants of the final instruction exist, chosen per model profile:

- `tags`: the model is told to think inside `<think></think>` (models
  without a native thinking mode, or with it switched off);
- `native`: the model's own thinking mode is on (chat-template switch), so
  the instruction only asks for the answer block.

`legal=False` drops the legal-move line (E5b). `prompt_hash()` is written into
every eval report and run record; it changes whenever any of this text does.
"""

from __future__ import annotations

import hashlib
from typing import Literal

import chess

from ks.data import primer

SYSTEM = primer.SYSTEM
Think = Literal["tags", "native"]

INSTRUCTION: dict[Think, str] = {
    "tags": (
        "Find the best move. Think it through inside <think></think>, then give\n"
        "exactly one move from the list, in SAN, inside <answer></answer>."
    ),
    "native": (
        "Find the best move. Think it through, then give exactly one move from\n"
        "the list, in SAN, inside <answer></answer>."
    ),
}
NO_LIST_INSTRUCTION: dict[Think, str] = {
    "tags": (
        "Find the best move. Think it through inside <think></think>, then give\n"
        "exactly one legal move, in SAN, inside <answer></answer>."
    ),
    "native": (
        "Find the best move. Think it through, then give exactly one legal move,\n"
        "in SAN, inside <answer></answer>."
    ),
}

# Hashed together with the template text, so a change to the framing is caught too.
_REFERENCE_FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


def user_text(board: chess.Board, think: Think = "tags", legal: bool = True) -> str:
    instr = (INSTRUCTION if legal else NO_LIST_INSTRUCTION)[think]
    return primer.user_prompt(board, instr, legal=legal)


def messages(board: chess.Board, think: Think = "tags", legal: bool = True) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text(board, think, legal)},
    ]


def prompt_hash(think: Think = "tags", legal: bool = True) -> str:
    """First 12 hex digits of sha256 over the rendered reference prompt."""
    msgs = messages(chess.Board(_REFERENCE_FEN), think, legal)
    blob = "\n\x1e".join(f"{m['role']}\x1f{m['content']}" for m in msgs)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
