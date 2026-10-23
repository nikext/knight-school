"""Arm-vs-arm comparisons of saved eval results (RESEARCH.md §5): paired bootstrap of the solve
rate on the puzzles both runs graded, the puzzles only one of them solved, and solve rates per
rating bin.

    ks compare results/eval/test2000/a.json.gz results/eval/test2000/b.json.gz --ref b
"""

from __future__ import annotations

from typing import Any

from ks.data.puzzles import BIN_WIDTH, RATING_LO
from ks.eval import harness
from ks.eval import metrics as m


def paired(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """solve(a) - solve(b) with a paired bootstrap CI, and who alone solved what."""
    va, vb = harness.solved_vector(a), harness.solved_vector(b)
    common = sorted(set(va) & set(vb))
    if not common:
        raise ValueError("no puzzles in common")
    ci = m.paired_diff_ci([va[p] for p in common], [vb[p] for p in common])
    return {
        "n": len(common),
        "delta": ci.as_dict(),
        "a_only": sum(va[p] > vb[p] for p in common),
        "b_only": sum(vb[p] > va[p] for p in common),
    }


def bin_label(i: int) -> str:
    lo = RATING_LO + i * BIN_WIDTH
    return f"{lo}-{lo + BIN_WIDTH - 1}"


def markdown(results: dict[str, dict[str, Any]], ref: str) -> str:
    names = list(results)
    lines = [
        "| Run | Solve | Δ vs " + ref + " (paired) | only this run | only " + ref + " |",
        "|---|---|---|---|---|",
    ]
    for n in names:
        s = results[n]["summary"]["solve"]
        cell = f"{100 * s['value']:.1f}% [{100 * s['lo']:.1f}, {100 * s['hi']:.1f}]"
        if n == ref:
            lines.append(f"| {n} | {cell} | — | | |")
            continue
        d = paired(results[n], results[ref])
        dd = d["delta"]
        lines.append(
            f"| {n} | {cell} | {100 * dd['value']:+.1f} [{100 * dd['lo']:+.1f}, {100 * dd['hi']:+.1f}] "
            f"| {d['a_only']} | {d['b_only']} |"
        )
    lines += [
        "",
        "| Rating bin | n | " + " | ".join(names) + " |",
        "|---|---|" + "---|" * len(names),
    ]
    bins = [results[n]["summary"]["bins"] for n in names]
    for i, row in enumerate(bins[0]):
        cells = [f"{100 * b[i]['solve']:.1f}%" for b in bins]
        lines.append(f"| {bin_label(row['bin'])} | {row['n']} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
