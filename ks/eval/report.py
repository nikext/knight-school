"""Write and read eval results: `results/eval/<set>/<run>.json[.gz]` plus a `.md` summary (EVALS.md §6)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ks.cloud.config import REPO
from ks.data.puzzles import BIN_WIDTH, RATING_LO

RESULTS_DIR = REPO / "results" / "eval"
GZIP_OVER_BYTES = 1_000_000  # the repo's pre-commit hook refuses files over 1 MB
EXAMPLE_CHARS = 700


def write(
    result: dict[str, Any],
    out_dir: Path = RESULTS_DIR,
    render: Callable[[dict[str, Any]], str] | None = None,
) -> tuple[Path, Path]:
    h = result["header"]
    d = out_dir / h["set"]
    d.mkdir(parents=True, exist_ok=True)
    blob = (json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    for stale in (d / f"{h['run']}.json", d / f"{h['run']}.json.gz"):
        stale.unlink(missing_ok=True)
    if len(blob) > GZIP_OVER_BYTES:
        jp = d / f"{h['run']}.json.gz"
        jp.write_bytes(gzip.compress(blob, mtime=0))
    else:
        jp = d / f"{h['run']}.json"
        jp.write_bytes(blob)
    md = d / f"{h['run']}.md"
    md.write_text((render or markdown)(result))
    return jp, md


def read(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def _ci(d: dict[str, float]) -> str:
    return f"{100 * d['value']:.1f}% [{100 * d['lo']:.1f}, {100 * d['hi']:.1f}]"


def rating_text(r: dict[str, Any]) -> str:
    if r["r50"] is None:
        return {"above": "> range", "below": "< range", "flat": "n/a (flat)"}.get(r["bound"], "n/a")
    if r["lo"] is None:
        return f"{r['r50']:.0f}"
    return f"{r['r50']:.0f} [{r['lo']:.0f}, {r['hi']:.0f}]"


def _decoding(p: dict[str, Any], n: int) -> str:
    if p["backend"] in ("random", "stockfish"):
        return "n/a (engine)" if p["backend"] == "stockfish" else f"seed {p['seed']}"
    if p["backend"] == "gemini":
        budget = p.get("thinking_budget")
        t = "provider default sampling, thinking budget " + (
            "default" if budget is None else str(budget)
        )
    elif p["temperature"] == 0:
        t = "greedy (T=0)"
    else:
        t = f"T={p['temperature']}, top_p={p['top_p']}"
    extra = f"; {n} samples at T=1.0 for pass@k" if n > 1 else ""
    return f"{t}, max {p['max_tokens']} tokens, think={p['think']}{extra}"


def _example(it: dict[str, Any]) -> list[str]:
    s = it["samples"][0]
    text = s["text"]
    if len(text) > EXAMPLE_CHARS:
        text = "…" + text[-EXAMPLE_CHARS:]
    return [
        f"**{it['id']}** (rating {it['rating']}), solution `{it['solution_san']}`, "
        f"answer `{s['san'] or '-'}` ({s['status']}, {'right' if s['correct'] else 'wrong'})",
        "",
        "````text",  # four backticks, so a model's own ``` fences can't close the block
        text,
        "````",
        "",
    ]


def examples(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Up to five: two right, two wrong-but-legal, one illegal or unanswered, in set order."""
    picks: list[dict[str, Any]] = []
    for want, k in (("right", 2), ("legal", 2), ("illegal", 1)):
        pool = [
            it
            for it in items
            if (want == "right" and it["samples"][0]["correct"])
            or (
                want == "legal"
                and not it["samples"][0]["correct"]
                and it["samples"][0]["status"] == "ok"
            )
            or (want == "illegal" and it["samples"][0]["status"] != "ok")
        ]
        step = max(1, len(pool) // k) if pool else 1
        picks.extend(pool[::step][:k])
    return picks


def markdown(result: dict[str, Any]) -> str:
    h, s = result["header"], result["summary"]
    p = h["profile"]
    model = p.get("hf_repo") or p.get("vertex_model") or p["backend"]
    if p["backend"] == "stockfish":
        model = f"{h.get('version', 'Stockfish')}, {p['nodes']} nodes"
    lines = [
        f"# {h['run']} on {h['set']}",
        "",
        f"- model: `{model}`" + (f" @ `{p['revision'][:12]}`" if p.get("revision") else ""),
        f"- profile: `{p['name']}`"
        + (f", checkpoint `{h['checkpoint']}`" if h["checkpoint"] else ""),
        f"- git `{h['git_sha']}`, prompt hash `{h['prompt_hash']}`, legal list {'on' if p['legal_list'] else 'off'}",
        f"- decoding: {_decoding(p, h['n_samples'])}",
        f"- run: {h['started']}, {h['seconds']:.0f} s, cost ${h['cost_usd']:.4f}"
        + (f" (${h['price_per_hour']:.3f}/h)" if h.get("price_per_hour") else ""),
    ]
    if h.get("stopped"):
        lines.append(f"- **stopped early:** {h['stopped']}")
    if not s.get("puzzles"):
        return "\n".join([*lines, "", "No puzzles graded.", ""])
    lines += [
        "",
        f"{s['puzzles']} puzzles, {s['positions']} positions. 95% bootstrap CIs over puzzles.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| solve rate | {_ci(s['solve'])} |",
        f"| move accuracy | {_ci(s['move_acc'])} |",
        f"| legal rate | {_ci(s['legal'])} |",
        f"| format rate | {_ci(s['format'])} |",
        f"| puzzle rating (50% solve) | {rating_text(s['rating'])} |",
        f"| response tokens mean / p95 | {s['tokens_out_mean']:.0f} / {s['tokens_out_p95']:.0f} |",
        f"| prompt tokens mean | {s['tokens_in_mean']:.0f} |",
        f"| hit max tokens | {100 * s['truncated']:.1f}% |",
        f"| $ per 1k puzzles | {s['usd_per_1k_puzzles']:.4f} |",
    ]
    if "pass_at" in s:
        lines.append(
            "| pass@k (T=1) | "
            + ", ".join(f"@{k} {100 * v:.1f}%" for k, v in s["pass_at"].items())
            + " |"
        )
    lines += ["", "| Rating bin | n | solve |", "|---|---|---|"]
    for b in s["bins"]:
        lo = RATING_LO + b["bin"] * BIN_WIDTH
        v = "-" if b["n"] == 0 else f"{100 * b['solve']:.1f}%"
        lines.append(f"| {lo}-{lo + BIN_WIDTH - 1} | {b['n']} | {v} |")
    if p["backend"] not in ("random", "stockfish"):
        lines += ["", "## Examples", ""]
        for it in examples(result["items"]):
            lines += _example(it)
    return "\n".join(lines).rstrip() + "\n"
