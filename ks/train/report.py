"""GRPO run results for the repo (task M3 §9): pull a run's outputs, write CSVs, draw figures.

    ks train-report m3-e2-dense            # gs://BUCKET/runs/<id>/attempts/*/out -> results/train/<id>/
    ks train-report m3-e2-sparse-v2 --continued-by m3-e2-sparse-v2-r2
    ks train-figures m3-e2-sparse m3-e2-dense --name e2

results/train/<id>/ gets `steps.csv` (one row per optimizer step, the last attempt's where a
resume repeated a step), `dev.csv` (one row per dev eval), each attempt's run.json, and
`samples.jsonl.gz` (the completions logged at a few steps, for the write-up and the M6 browser).
A run finished under a new id (the gate never reuses one) from a copy of the first run's
checkpoint is merged with `--continued-by`, as if it were a further attempt.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import polars as pl

from ks.cloud.config import REPO
from ks.train import metrics as km

RESULTS = REPO / "results" / "train"
FIGURES = REPO / "results" / "figures"
SAMPLE_STEPS = (1, 25, 50, 100, 150, 200)

# reference palette (dataviz skill): categorical slots in fixed order, one per run as listed,
# and neutral ink. Slots 1-3 validate all-pairs on SURFACE; slot 3 is under 3:1 contrast, so
# the legend and end-of-line labels carry identity too.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def _shift(rows: list[dict[str, Any]], attempts: int, usd: float) -> None:
    for r in rows:
        if "attempt" in r:
            r["attempt"] = int(r["attempt"]) + attempts
        if r.get("usd_cum") is not None:
            r["usd_cum"] = float(r["usd_cum"]) + usd


def collect(runs: list[list[Path]], dest: Path) -> dict[str, int]:
    """Merge the attempts' outputs (each an `out/` dir, one list per run id) into dest.

    A run after the first continued the one before it from a copied checkpoint: its attempts are
    numbered after the earlier run's, and its dollar counts carry on from the earlier total.
    Returns row counts.
    """
    dest.mkdir(parents=True, exist_ok=True)
    steps, dev, samples = [], [], []
    attempts, usd = 0, 0.0
    for outs in runs:
        run_steps, run_dev = [], []
        for out in outs:
            run_steps += km.read_rows(sorted((out / "metrics").glob("attempt-*.jsonl")))
            run_dev += km.read_rows(sorted((out / "metrics").glob("dev-attempt-*.jsonl")))
            samples += km.read_rows(sorted((out / "samples").glob("attempt-*.jsonl")))
            for p in sorted((out / "run").glob("attempt-*.json")):
                n = int(p.stem.removeprefix("attempt-")) + attempts
                (dest / f"run-attempt-{n}.json").write_text(p.read_text().rstrip("\n") + "\n")
        _shift(run_steps + run_dev, attempts, usd)
        steps, dev = steps + run_steps, dev + run_dev
        attempts = max(
            (int(r["attempt"]) for r in run_steps + run_dev if "attempt" in r), default=attempts
        )
        usd = max((float(r.get("usd_cum") or 0) for r in run_steps + run_dev), default=usd)
    steps, dev = km.last_per_step(steps), km.last_per_step(dev)
    if steps:
        pl.DataFrame(steps, infer_schema_length=None).write_csv(dest / "steps.csv")
    if dev:
        pl.DataFrame(dev, infer_schema_length=None).write_csv(dest / "dev.csv")
    keep = [s for s in samples if s.get("step") in SAMPLE_STEPS]
    with gzip.open(dest / "samples.jsonl.gz", "wt") as f:
        for s in keep:
            f.write(json.dumps(s) + "\n")
    return {"steps": len(steps), "dev": len(dev), "samples": len(keep)}


def pull(
    run_id: str, bucket: str, dest: Path | None = None, continued_by: tuple[str, ...] = ()
) -> dict[str, int]:
    """Download every attempt's metrics, run.json and samples for a run (and the runs that
    continued it), then collect them."""
    import tempfile

    from ks.cloud import gcs

    tmp = Path(tempfile.mkdtemp(prefix=f"ks-{run_id}-"))
    runs = []
    for rid in (run_id, *continued_by):
        root = f"{bucket.rstrip('/')}/runs/{rid}/attempts"
        names = gcs.list_names(root + "/")
        bucket_name, prefix = gcs.split(root + "/")
        outs = set()
        for n in names:
            rel = n.removeprefix(prefix)  # <attempt>/out/<kind>/<file>
            parts = rel.split("/")
            if len(parts) >= 4 and parts[1] == "out" and parts[2] in ("metrics", "run", "samples"):
                gcs.download(f"gs://{bucket_name}/{n}", tmp / rid / rel)
                outs.add(tmp / rid / parts[0] / "out")
        runs.append(sorted(outs, key=lambda o: int(o.parent.name)))
    return collect(runs, dest or RESULTS / run_id)


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def figures(
    run_ids: list[str],
    name: str,
    base_solve: float | None = None,
    roles: dict[str, str] | None = None,
) -> list[Path]:
    """Dev solve rate vs dollars (all runs on one axis) and reward components vs step."""
    import matplotlib  # type: ignore[import-not-found]

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore[import-not-found]

    if len(run_ids) > len(SERIES):
        raise ValueError(f"at most {len(SERIES)} runs per figure; split them into several")
    FIGURES.mkdir(parents=True, exist_ok=True)
    runs = {r: (RESULTS / r) for r in run_ids}
    color: dict[str, str] = dict(zip(run_ids, SERIES, strict=False))
    style = dict.fromkeys(run_ids, "-")
    label = {r: r for r in run_ids}
    if roles:  # colour = start point, line style = reward (ks.eval.compare.ROLES)
        from ks.eval.compare import ROLES

        for r, role in roles.items():
            text, slot, ls = ROLES[role]
            color[r], style[r], label[r] = (INK_2 if slot is None else SERIES[slot]), ls, text
    paths = []

    fig, ax = plt.subplots(figsize=(6.4, 4.0), facecolor=SURFACE)
    _style(ax)
    ends: list[tuple[float, float]] = []  # (usd, solve %) of each run's last dev eval
    for r, d in runs.items():
        dev = pl.read_csv(d / "dev.csv")
        c = color[r]
        ax.fill_between(
            dev["usd_cum"], dev["solve_lo"] * 100, dev["solve_hi"] * 100, color=c, alpha=0.15, lw=0
        )
        ax.plot(
            dev["usd_cum"],
            dev["solve"] * 100,
            color=c,
            ls=style[r],
            lw=2,
            marker="o",
            ms=4,
            label=label[r],
        )
        ends.append((dev["usd_cum"][-1], dev["solve"][-1] * 100))
    # End labels, nudged apart vertically so close finishes don't print over each other.
    lo, hi = ax.get_ylim()
    gap, dx = 0.035 * (hi - lo), 0.012 * (ax.get_xlim()[1] - ax.get_xlim()[0])
    placed: list[float] = []
    for x, y in sorted(ends, key=lambda e: e[1]):
        ty = max(y, placed[-1] + gap) if placed else y
        placed.append(ty)
        ax.annotate(
            f"{y:.1f}%",
            (x, y),
            xytext=(x + dx, ty),
            textcoords="data",
            fontsize=8,
            color=INK,
            va="center",
            ha="left",
        )
    if base_solve is not None:
        ax.axhline(base_solve * 100, color=INK_2, lw=1, ls="--")
        ax.annotate(
            "base model",
            (0, base_solve * 100),
            xytext=(2, 3),
            textcoords="offset points",
            fontsize=8,
            color=INK_2,
        )
    ax.set_xlabel("dollars spent (spot GPU wall time)", color=INK, fontsize=9)
    ax.set_ylabel("dev500 solve rate, greedy (%)", color=INK, fontsize=9)
    ax.set_title("Dev solve rate vs dollars, with 95% CI", color=INK, fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    p = FIGURES / f"{name}_dev_vs_usd.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    paths.append(p)

    panels = [  # (column, title, log y)
        ("sparse_mean", "move-match rate in training (T = 1)", False),
        ("legal_rate", "legal rate", False),
        ("format_rate", "format rate", False),
        ("len_mean", "completion tokens (mean, log)", True),
        ("truncated", "share truncated at max tokens", False),
        ("prose_frac", "share with prose before <answer>", False),
        ("entropy", "mean token entropy", False),
        ("frac_zero_std", "share of groups with no reward spread", False),
        ("kl", "KL to the base policy (log)", True),
    ]
    fig, axes = plt.subplots(3, 3, figsize=(10, 7.6), facecolor=SURFACE)
    for ax, (col, title, log) in zip(axes.flat, panels, strict=True):
        _style(ax)
        for r, d in runs.items():
            s = pl.read_csv(d / "steps.csv")
            # before ADR-022, TRL's clipped ratio was the truncated share
            col_r = "clipped" if col == "truncated" and col not in s.columns else col
            if col_r in s.columns:
                ax.plot(s["step"], s[col_r], color=color[r], ls=style[r], lw=1.5, label=label[r])
        if log:
            ax.set_yscale("log")
        ax.set_title(title, color=INK, fontsize=9, loc="left")
        ax.set_xlabel("step", color=INK_2, fontsize=8)
    axes.flat[0].legend(frameon=False, fontsize=7, labelcolor=INK)
    fig.tight_layout()
    p = FIGURES / f"{name}_components.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    paths.append(p)
    return paths
