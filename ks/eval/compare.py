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


# Figure roles: colour = where RL starts (validated all-pairs on SURFACE, dataviz skill), line
# style = the reward. The zero-shot base model is a neutral reference.
ROLES: dict[str, tuple[str, int | None, str]] = {
    "base": ("base, zero-shot", None, ":"),
    "e2_dense": ("base → GRPO dense", 0, "-"),
    "e2_sparse": ("base → GRPO sparse", 0, "--"),
    "primer": ("primer-M only", 2, "-"),
    "primer_dense": ("primer-M → GRPO dense", 1, "-"),
    "primer_sparse": ("primer-M → GRPO sparse", 1, "--"),
}


def bin_deltas(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, float]]:
    """Per rating bin: solve(a) - solve(b), paired by puzzle, with a bootstrap CI."""
    ta, tb = harness._puzzle_table(a["items"], 1), harness._puzzle_table(b["items"], 1)
    common = sorted(set(ta) & set(tb))
    out = []
    for i in sorted({ta[p]["bin"] for p in common}):
        ps = [p for p in common if ta[p]["bin"] == i]
        ci = m.paired_diff_ci(
            [float(ta[p]["ok"][0]) for p in ps], [float(tb[p]["ok"][0]) for p in ps]
        )
        out.append({"bin": i, "n": len(ps), **ci.as_dict()})
    return out


def bins_figure(results: dict[str, dict[str, Any]], path: Any, ref: str = "e2_dense") -> Any:
    """Solve rate per rating bin for each arm, and each primer arm's paired Δ vs `ref` per bin."""
    import matplotlib  # type: ignore[import-not-found]

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    from ks.train.report import INK, INK_2, SERIES, SURFACE, _style

    unknown = set(results) - set(ROLES)
    if unknown:
        raise ValueError(f"unknown roles {sorted(unknown)}; known: {list(ROLES)}")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.0), facecolor=SURFACE)
    n_bins = len(next(iter(results.values()))["summary"]["bins"])
    ticks = list(range(n_bins))
    tick_labels = [bin_label(i).split("-")[0] for i in ticks]
    for ax in (ax1, ax2):
        _style(ax)
        ax.set_xticks(ticks, tick_labels, rotation=45)
        ax.set_xlabel("puzzle rating (bin start)", color=INK, fontsize=9)

    for role, (label, slot, ls) in ROLES.items():
        if role not in results:
            continue
        c = INK_2 if slot is None else SERIES[slot]
        ys = [100 * b["solve"] for b in results[role]["summary"]["bins"]]
        lw = 1.5 if slot is None else 2
        ax1.plot(ticks, ys, color=c, ls=ls, lw=lw, marker="o", ms=4, label=label)
    ax1.set_ylabel("test2000 solve rate (%)", color=INK, fontsize=9)
    ax1.set_title("Solve rate per rating bin", color=INK, fontsize=10, loc="left")
    ax1.legend(frameon=False, fontsize=8, labelcolor=INK, handlelength=3.2)

    ax2.axhline(0, color=INK_2, lw=1)
    if ref in results:
        for role in ("primer", "primer_dense", "primer_sparse"):
            if role not in results:
                continue
            label, slot, ls = ROLES[role]
            assert slot is not None
            d = bin_deltas(results[role], results[ref])
            xs = [r["bin"] for r in d]
            c = SERIES[slot]
            ax2.fill_between(
                xs,
                [100 * r["lo"] for r in d],
                [100 * r["hi"] for r in d],
                color=c,
                alpha=0.15,
                lw=0,
            )
            ax2.plot(
                xs,
                [100 * r["value"] for r in d],
                color=c,
                ls=ls,
                lw=2,
                marker="o",
                ms=4,
                label=label,
            )
        ax2.legend(frameon=False, fontsize=8, labelcolor=INK, handlelength=3.2)
    ax2.set_ylabel(f"Δ solve vs {ROLES[ref][0]} (points)", color=INK, fontsize=9)
    ax2.set_title("Paired difference per bin, with 95% CI", color=INK, fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
