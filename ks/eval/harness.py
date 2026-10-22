"""The puzzle eval harness (EVALS.md §3): prompts -> backend -> parser -> metrics -> report.

Each solver position is its own prompt. Opponent replies come from the
solution, and a wrong move ends a puzzle, so the positions after a wrong move
don't count; scoring every position independently and calling a puzzle solved
when all its positions are right gives exactly the sequential result.

With `n > 1` samples (pass@k, dev only), sample j of a puzzle is "all
positions' j-th samples right"; sample 0 is the one the headline rates use.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import chess
import numpy as np

from ks.chess import prompt as kpr
from ks.chess import rewards as kr
from ks.data.manifest import git_sha
from ks.eval import metrics as m
from ks.eval.backends import Backend, Request
from ks.eval.profile import Profile
from ks.eval.sets import N_BINS, Puzzle

CHUNK = 512  # requests per backend call; the cost cap is checked between chunks
PASS_K = (1, 4, 8)


@dataclass
class EvalRun:
    profile: Profile
    set_name: str
    puzzles: list[Puzzle]
    n: int = 1
    max_usd: float | None = None
    checkpoint: str | None = None
    run_name: str | None = None
    log: Callable[[str], None] = field(default=lambda s: None)


def requests_for(profile: Profile, puzzles: list[Puzzle]) -> list[Request]:
    reqs = []
    for p in puzzles:
        for pos in p.positions:
            b = chess.Board(pos["fen"])
            msgs = kpr.messages(b, profile.think, profile.legal_list)
            reqs.append(Request(f"{p.id}-{pos['ply']}", b, msgs))
    return reqs


def run(cfg: EvalRun, backend: Backend) -> dict[str, Any]:
    """Generate and grade. Returns the full result (header, items, summary)."""
    t0 = time.monotonic()
    started = datetime.now(UTC).replace(microsecond=0)
    reqs = requests_for(cfg.profile, cfg.puzzles)
    outs: list[list[Any]] = []
    stopped = None
    for i in range(0, len(reqs), CHUNK):
        if cfg.max_usd is not None and backend.cost_usd >= cfg.max_usd:
            stopped = (
                f"cost cap ${cfg.max_usd:.2f} reached after {len(outs)} of {len(reqs)} prompts"
            )
            cfg.log(stopped)
            break
        outs.extend(backend.generate(reqs[i : i + CHUNK], cfg.n))
        cfg.log(f"{len(outs)}/{len(reqs)} prompts, ${backend.cost_usd:.4f}")

    by_id = {r.id: (r, o) for r, o in zip(reqs, outs, strict=False)}
    items = []
    for p in cfg.puzzles:
        # a puzzle cut off by the cost cap is left out entirely, not graded on part of its moves
        if any(f"{p.id}-{pos['ply']}" not in by_id for pos in p.positions):
            continue
        for pos in p.positions:
            rid = f"{p.id}-{pos['ply']}"
            req, comps = by_id[rid]
            target = kr.Target(req.board, chess.Move.from_uci(pos["solution_uci"]), pos["is_last"])
            samples = []
            for c in comps:
                r = kr.score(c.text, target, cfg.profile.require_think)
                samples.append(
                    {
                        "text": c.text,
                        "status": r.parsed.status,
                        "san": r.parsed.san,
                        "correct": bool(r.sparse),
                        "well_formed": bool(r.format),
                        "tokens_in": c.tokens_in,
                        "tokens_out": c.tokens_out,
                        "finish": c.finish,
                    }
                )
            items.append(
                {
                    "id": rid,
                    "puzzle_id": p.id,
                    "ply": pos["ply"],
                    "rating": p.rating,
                    "bin": p.bin,
                    "fen": pos["fen"],
                    "solution_san": pos["solution_san"],
                    "is_last": pos["is_last"],
                    "samples": samples,
                }
            )
    header = {
        "set": cfg.set_name,
        "run": cfg.run_name or f"{cfg.profile.name}",
        "profile": cfg.profile.model_dump(exclude_defaults=False),
        "checkpoint": cfg.checkpoint,
        "git_sha": git_sha(),
        "prompt_hash": kpr.prompt_hash(cfg.profile.think, cfg.profile.legal_list),
        "n_samples": cfg.n,
        "started": started.isoformat().replace("+00:00", "Z"),
        "seconds": round(time.monotonic() - t0, 1),
        "cost_usd": round(backend.cost_usd, 6),
        "stopped": stopped,
    }
    for attr in ("version", "load_seconds", "gen_seconds", "price_per_hour"):
        if hasattr(backend, attr):
            header[attr] = getattr(backend, attr)
    return {"header": header, "summary": summarise(items, cfg.n, backend.cost_usd), "items": items}


# the profile fields that shape generation; a rescore may change any of the others
_GENERATION_FIELDS = ("hf_repo", "revision", "vertex_model", "think", "legal_list", "max_tokens")


def rescore(result: dict[str, Any], profile: Profile, reason: str) -> dict[str, Any]:
    """Re-grade a saved result's texts under `profile` (a changed grading rule), at no cost.

    Only grading may differ: the generation fields must match the saved profile. The header
    keeps the original run's git sha and records the rescore.
    """
    saved = result["header"]["profile"]
    now = profile.model_dump(exclude_defaults=False)
    diff = [f for f in _GENERATION_FIELDS if saved.get(f) != now.get(f)]
    if diff:
        raise ValueError(f"profile {profile.name} differs from the saved run in {diff}")
    items = []
    for it in result["items"]:
        board = chess.Board(it["fen"])
        sol = board.parse_san(it["solution_san"])
        target = kr.Target(board, sol, it["is_last"])
        samples = []
        for s in it["samples"]:
            r = kr.score(s["text"], target, profile.require_think)
            samples.append(
                {
                    **s,
                    "status": r.parsed.status,
                    "san": r.parsed.san,
                    "correct": bool(r.sparse),
                    "well_formed": bool(r.format),
                }
            )
        items.append({**it, "samples": samples})
    header = {
        **result["header"],
        "profile": now,
        "rescored": {
            "git_sha": git_sha(),
            "at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "reason": reason,
        },
    }
    cost = result["header"]["cost_usd"]
    return {
        "header": header,
        "summary": summarise(items, header["n_samples"], cost),
        "items": items,
    }


def _puzzle_table(items: list[dict[str, Any]], n: int) -> dict[str, dict[str, Any]]:
    """Per puzzle: rating, bin, positions, and per sample index whether every position was right."""
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        p = out.setdefault(
            it["puzzle_id"],
            {"rating": it["rating"], "bin": it["bin"], "pos": 0, "ok": [True] * n},
        )
        p["pos"] += 1
        for j, s in enumerate(it["samples"][:n]):
            p["ok"][j] = p["ok"][j] and s["correct"]
    return out


def summarise(items: list[dict[str, Any]], n: int = 1, cost_usd: float = 0.0) -> dict[str, Any]:
    if not items:
        return {"puzzles": 0, "positions": 0}
    puzzles = _puzzle_table(items, n)
    pids = list(puzzles)
    per = {pid: {"correct": 0, "legal": 0, "format": 0} for pid in pids}
    toks_out, toks_in, truncated = [], [], 0
    for it in items:
        s = it["samples"][0]
        d = per[it["puzzle_id"]]
        d["correct"] += s["correct"]
        d["legal"] += s["status"] == "ok"
        d["format"] += s["well_formed"]
        toks_out.append(s["tokens_out"])
        toks_in.append(s["tokens_in"])
        truncated += s["finish"] == "length"
    den = [puzzles[p]["pos"] for p in pids]
    solved = [float(puzzles[p]["ok"][0]) for p in pids]
    ratings = [puzzles[p]["rating"] for p in pids]
    fit = m.rating_fit(ratings, solved)
    out: dict[str, Any] = {
        "puzzles": len(pids),
        "positions": len(items),
        "solve": m.mean_ci(solved).as_dict(),
        "move_acc": m.ratio_ci([per[p]["correct"] for p in pids], den).as_dict(),
        "legal": m.ratio_ci([per[p]["legal"] for p in pids], den).as_dict(),
        "format": m.ratio_ci([per[p]["format"] for p in pids], den).as_dict(),
        "rating": {
            "r50": fit.r50,
            "lo": fit.lo,
            "hi": fit.hi,
            "bound": fit.bound,
            "slope_per_100": fit.slope_per_100,
        },
        "bins": m.per_bin([puzzles[p]["bin"] for p in pids], solved, N_BINS),
        "tokens_out_mean": float(np.mean(toks_out)),
        "tokens_out_p95": float(np.percentile(toks_out, 95)),
        "tokens_in_mean": float(np.mean(toks_in)),
        "truncated": truncated / len(items),
        "cost_usd": cost_usd,
        "usd_per_1k_puzzles": 1000 * cost_usd / len(pids),
    }
    if n > 1:
        out["pass_at"] = {
            str(k): float(np.mean([m.pass_at_k(n, sum(puzzles[p]["ok"]), k) for p in pids]))
            for k in PASS_K
            if k <= n
        }
    return out


def solved_vector(result: dict[str, Any]) -> dict[str, float]:
    """puzzle id -> solved (sample 0), for paired comparisons."""
    table = _puzzle_table(result["items"], 1)
    return {pid: float(p["ok"][0]) for pid, p in table.items()}


def compare(a: dict[str, Any], b: dict[str, Any]) -> m.CI:
    """Paired bootstrap of solve(a) - solve(b) on the puzzles both runs graded."""
    va, vb = solved_vector(a), solved_vector(b)
    common = sorted(set(va) & set(vb))
    if not common:
        raise ValueError("no puzzles in common")
    return m.paired_diff_ci([va[p] for p in common], [vb[p] for p in common])
