"""Data for the puzzle browser (site/, M6 task 4): every test2000 puzzle with each model's answer
at each solver position, from the saved eval results. $0: nothing is generated, the answers are
the ones the harness graded.

    ks browser-data   # writes site/public/data/puzzles.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chess

from ks.cloud.config import REPO
from ks.eval import harness, report, sets
from ks.eval.compare import bin_label

RESULTS = REPO / "results" / "eval" / "test2000"
OUT = REPO / "site" / "public" / "data" / "puzzles.json"
ANSWER = re.compile(r"<answer>(.*?)(?:</answer>|$)", re.S)


@dataclass(frozen=True)
class Model:
    key: str
    run: str
    label: str
    blurb: str


# Same reward (sparse) and config (v3) for both RL arms: they differ only in the start point.
MODELS = (
    Model("base", "qwen3.5-2b", "Base", "Qwen3.5-2B zero-shot, non-thinking"),
    Model("rl", "m4-e2-sparse-v3", "Base → RL", "GRPO from the base model (E2, sparse reward)"),
    Model("primer", "m4-sft-primer-m-t8", "Primer", "SFT on the primer-M set only (E3)"),
    Model("primer_rl", "m4-e3-sparse", "Primer → RL", "GRPO from the primer model (E3, sparse)"),
    Model("stockfish", "stockfish-1node", "Stockfish", "Stockfish 19 at 1 node, reference"),
)


def _shown(sample: dict[str, Any]) -> str:
    """What the model answered, as text: its SAN if graded legal, else the raw answer."""
    if sample.get("san"):
        return str(sample["san"])
    m = ANSWER.search(sample.get("text", ""))
    raw = (m.group(1) if m else sample.get("text", "")).strip()
    return raw[:24] or "—"


def _uci(fen: str, san: str | None) -> str | None:
    if not san:
        return None
    try:
        return chess.Board(fen).parse_san(san).uci()
    except ValueError:
        return None


def build(
    results: dict[str, dict[str, Any]],
    puzzles: list[sets.Puzzle],
    csv_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """The browser's JSON: models with their test2000 summary, and per puzzle the moves and answers.

    `a[i][j]` is model j's answer at solver position i: [shown text, uci or null, correct 0/1].
    """
    by_item = {m.key: {it["id"]: it for it in results[m.key]["items"]} for m in MODELS}
    solved = {m.key: harness.solved_vector(results[m.key]) for m in MODELS}
    out_puzzles = []
    for p in puzzles:
        row = csv_rows[p.id]
        answers = []
        for pos in p.positions:
            iid = f"{p.id}-{pos['ply']}"
            cells = []
            for m in MODELS:
                it = by_item[m.key][iid]
                if it["fen"] != pos["fen"]:
                    raise ValueError(f"{m.run}: {iid} graded a different position")
                s = it["samples"][0]
                cells.append([_shown(s), _uci(it["fen"], s.get("san")), int(bool(s["correct"]))])
            answers.append(cells)
        out_puzzles.append(
            {
                "id": p.id,
                "r": p.rating,
                "b": p.bin,
                "t": row["Themes"].split(),
                "fen": row["FEN"],
                "m": row["Moves"].split(),
                "s": [int(solved[m.key][p.id]) for m in MODELS],
                "a": answers,
            }
        )
    models = []
    for m in MODELS:
        summ = results[m.key]["summary"]
        rate = sum(solved[m.key].values()) / len(solved[m.key])
        if abs(rate - summ["solve"]["value"]) > 1e-9:
            raise ValueError(f"{m.run}: solve {rate} != summary {summ['solve']['value']}")
        models.append(
            {
                "key": m.key,
                "label": m.label,
                "blurb": m.blurb,
                "run": m.run,
                "solve": summ["solve"],
                "move_acc": summ["move_acc"]["value"],
                "legal": summ["legal"]["value"],
            }
        )
    return {
        "set": "test2000",
        "bins": [bin_label(i) for i in range(sets.N_BINS)],
        "models": models,
        "puzzles": out_puzzles,
    }


def write(out: Path = OUT, results_dir: Path = RESULTS, sets_dir: Path = sets.SETS_DIR) -> Path:
    import polars as pl

    results = {m.key: report.read(results_dir / f"{m.run}.json.gz") for m in MODELS}
    puzzles = sets.load_puzzles("test2000", sets_dir)
    df = pl.read_csv(sets_dir / "test2000.csv", schema_overrides={"PuzzleId": pl.String})
    rows = {r["PuzzleId"]: r for r in df.iter_rows(named=True)}
    data = build(results, puzzles, rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n")
    return out
