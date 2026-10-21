"""probe500 (EVALS.md §4): 125 items each of P1-P4 on held-out eval-DB positions.

The questions and answers come from the primer generators, so a primer
checkpoint is probed in exactly the format it was taught. The probe
positions go into the blocklist, which keeps them out of the primer.
"""

from __future__ import annotations

import random

import polars as pl

from ks.data import primer as pr
from ks.data.puzzles import order_key

SEED = 2026
PER_TASK = 125
TASKS: dict[str, pr.Gen] = {
    "P1": pr.t1_square,
    "P2": pr.t2_all,
    "P3": pr.t3_effect,
    "P4": pr.t4_check,
}
COLUMNS = ["id", "task", "fen", "question", "answer", "move"]


def build(sample: pl.DataFrame, seed: int = SEED) -> pl.DataFrame:
    """sample: the eval-DB reservoir (fen, cp, mate, line). P4 is half in check, half not."""
    keys = [order_key(seed, f"probe:{n}") for n in sample["line_no"].to_list()]
    order = sorted(range(sample.height), key=keys.__getitem__)
    src = pr.evaldb_source(
        sample.select("fen", "cp", "mate", "line").to_dict(as_series=False), order
    )
    rng = random.Random(seed)
    rows = []
    for task, gen in TASKS.items():
        for i in range(PER_TASK):
            if task == "P4":
                want = i % 2 == 0
                pos = src.take(f"check={want}", lambda p, w=want: p.board.is_check() == w)
            else:
                pos = src.take()
            item = gen(pos, rng)
            assert item is not None
            rows.append(
                {
                    "id": f"{task}-{i:03d}",
                    "task": task,
                    "fen": item.board.fen(),
                    "question": item.question,
                    "answer": item.answer,
                    "move": item.move,
                }
            )
    return pl.DataFrame(rows).select(COLUMNS)
