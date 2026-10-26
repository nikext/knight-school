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


def scaling_figure(
    none: tuple[dict[str, Any], dict[str, Any]],
    points: list[tuple[str, float, dict[str, Any], dict[str, Any]]],
    path: Any,
) -> Any:
    """E4: test2000 solve rate vs primer tokens (log x), primer only and primer → GRPO dense, with
    95% CIs. `none` is (base zero-shot, base → GRPO dense), drawn in its own panel at "no primer"
    since log x has no 0. `points` are (name, tokens, primer only, primer → GRPO)."""
    import matplotlib  # type: ignore[import-not-found]

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    from ks.train.report import GRID, INK, SERIES, SURFACE, _style

    def ci(r: dict[str, Any]) -> tuple[float, float, float]:
        s = r["summary"]["solve"]
        return 100 * s["value"], 100 * (s["value"] - s["lo"]), 100 * (s["hi"] - s["value"])

    fig, (ax0, ax1) = plt.subplots(
        1,
        2,
        figsize=(7.5, 4.0),
        sharey=True,
        gridspec_kw={"width_ratios": [1, 4], "wspace": 0.06},
        facecolor=SURFACE,
    )
    for ax in (ax0, ax1):
        _style(ax)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    ax1.spines["left"].set_visible(False)
    ax1.tick_params(axis="y", length=0)

    series = (
        ("primer only (SFT)", SERIES[2], [p[2] for p in points], "--"),
        ("→ GRPO dense", SERIES[1], [p[3] for p in points], "-"),
    )
    xs = [p[1] for p in points]
    ends = [ci(s[2][-1])[0] for s in series]
    for k, ((label, c, runs, ls), base) in enumerate(zip(series, none, strict=True)):
        dodge = (-1, 1)[k]  # the two series share x; offset them so the CIs don't overlap
        y, lo, hi = ci(base)
        ax0.errorbar(
            [0.08 * dodge], [y], yerr=[[lo], [hi]], color=c, marker="o", ms=7, capsize=3, lw=2
        )
        ys = [ci(r) for r in runs]
        ax1.errorbar(
            [x * 1.04**dodge for x in xs],
            [v[0] for v in ys],
            yerr=[[v[1] for v in ys], [v[2] for v in ys]],
            color=c,
            ls=ls,
            marker="o",
            ms=7,
            capsize=3,
            lw=2,
            label=label,
        )
        above = ends[k] >= ends[1 - k]
        ax1.annotate(
            f"{ys[-1][0]:.1f}%",
            (xs[-1] * 1.04**dodge, ys[-1][0]),
            xytext=(10, 7 if above else -7),
            textcoords="offset points",
            va="center",
            color=INK,
            fontsize=8,
        )
    ax0.set_xticks([0], ["none\n(base)"])
    ax0.set_xlim(-0.6, 0.6)
    ax0.set_ylabel("test2000 solve rate (%)", color=INK, fontsize=9)
    ax0.set_ylim(0, None)
    ax1.set_xscale("log")
    ax1.set_xlim(min(xs) / 2, max(xs) * 2.5)
    ax1.set_xticks(xs, [f"{p[0]}\n{p[1] / 1e6:.0f}M" for p in points])
    ax1.minorticks_off()
    ax1.set_xlabel("primer tokens (log scale)", color=INK, fontsize=9)
    ax1.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")
    fig.suptitle(
        "E4: solve rate vs primer size, with 95% CIs", color=INK, fontsize=10, x=0.08, ha="left"
    )
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return path
