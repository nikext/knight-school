"""GRPO run results for the repo (task M3 §9): pull a run's outputs, write CSVs, draw figures.

    ks train-report m3-e2-dense            # gs://BUCKET/runs/<id>/attempts/*/out -> results/train/<id>/
    ks train-figures m3-e2-sparse m3-e2-dense --name e2

results/train/<id>/ gets `steps.csv` (one row per optimizer step, the last attempt's where a
resume repeated a step), `dev.csv` (one row per dev eval), each attempt's run.json, and
`samples.jsonl.gz` (the completions logged at a few steps, for the write-up and the M6 browser).
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

# reference palette, categorical slots 1-2, and neutral ink (dataviz skill)
ARM_COLORS = {"dense": "#2a78d6", "sparse": "#eb6834"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def collect(out_dirs: list[Path], dest: Path) -> dict[str, int]:
    """Merge the attempts' outputs (each an `out/` dir) into dest. Returns row counts."""
    dest.mkdir(parents=True, exist_ok=True)
    steps, dev, samples = [], [], []
    for out in out_dirs:
        steps += km.read_rows(sorted((out / "metrics").glob("attempt-*.jsonl")))
        dev += km.read_rows(sorted((out / "metrics").glob("dev-attempt-*.jsonl")))
        samples += km.read_rows(sorted((out / "samples").glob("attempt-*.jsonl")))
        for p in sorted((out / "run").glob("attempt-*.json")):
            (dest / f"run-{p.name}").write_text(p.read_text().rstrip("\n") + "\n")
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


def pull(run_id: str, bucket: str, dest: Path | None = None) -> dict[str, int]:
    """Download every attempt's metrics, run.json and samples for a run, then collect them."""
    import tempfile

    from ks.cloud import gcs

    root = f"{bucket.rstrip('/')}/runs/{run_id}/attempts"
    tmp = Path(tempfile.mkdtemp(prefix=f"ks-{run_id}-"))
    names = gcs.list_names(root + "/")
    bucket_name, prefix = gcs.split(root + "/")
    outs = set()
    for n in names:
        rel = n.removeprefix(prefix)  # <attempt>/out/<kind>/<file>
        parts = rel.split("/")
        if len(parts) >= 4 and parts[1] == "out" and parts[2] in ("metrics", "run", "samples"):
            gcs.download(f"gs://{bucket_name}/{n}", tmp / rel)
            outs.add(tmp / parts[0] / "out")
    return collect(sorted(outs), dest or RESULTS / run_id)


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _arm(run_id: str) -> str:
    return "sparse" if "sparse" in run_id else "dense"


def figures(run_ids: list[str], name: str, base_solve: float | None = None) -> list[Path]:
    """Dev solve rate vs dollars (all runs on one axis) and reward components vs step."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)
    runs = {r: (RESULTS / r) for r in run_ids}
    paths = []

    fig, ax = plt.subplots(figsize=(6.4, 4.0), facecolor=SURFACE)
    _style(ax)
    for r, d in runs.items():
        dev = pl.read_csv(d / "dev.csv")
        c = ARM_COLORS[_arm(r)]
        ax.fill_between(
            dev["usd_cum"], dev["solve_lo"] * 100, dev["solve_hi"] * 100, color=c, alpha=0.15, lw=0
        )
        ax.plot(dev["usd_cum"], dev["solve"] * 100, color=c, lw=2, marker="o", ms=4, label=r)
        ax.annotate(
            f"{dev['solve'][-1] * 100:.1f}%",
            (dev["usd_cum"][-1], dev["solve"][-1] * 100),
            xytext=(4, 0),
            textcoords="offset points",
            fontsize=8,
            color=INK,
            va="center",
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

    panels = [
        ("task reward (mean)", None),
        ("legal_rate", "legal rate"),
        ("format_rate", "format rate"),
        ("len_mean", "completion tokens (mean)"),
        ("prose_frac", "share with prose before <answer>"),
        ("kl", "KL to the base policy"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.4), facecolor=SURFACE)
    for ax, (col, title) in zip(axes.flat, panels, strict=True):
        _style(ax)
        for r, d in runs.items():
            s = pl.read_csv(d / "steps.csv")
            key = f"{_arm(r)}_mean" if col.startswith("task") else col
            if key in s.columns:
                ax.plot(s["step"], s[key], color=ARM_COLORS[_arm(r)], lw=1.5, label=r)
        ax.set_title(
            title or f"task reward ({'/'.join(sorted({_arm(r) for r in runs}))})",
            color=INK,
            fontsize=9,
            loc="left",
        )
        ax.set_xlabel("step", color=INK_2, fontsize=8)
    axes.flat[0].legend(frameon=False, fontsize=7, labelcolor=INK)
    fig.tight_layout()
    p = FIGURES / f"{name}_components.png"
    fig.savefig(p, dpi=160)
    plt.close(fig)
    paths.append(p)
    return paths
