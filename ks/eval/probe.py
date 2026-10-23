"""E0 knowledge probe on probe500 (EVALS.md §4).

The user turn is the primer's (`Position (FEN)`, `Side to move`, question),
so a primer checkpoint sees what it was taught. A zero-shot model has never
seen the answer formats, so one fixed format line per task follows the
question for **every** model. The grader then reads the answer from the
`<answer>` block if there is one (the reply ends at the first `</answer>`, as in
every eval: ADR-022), else from the text after `</think>`, else the whole reply.

| Task | Graded |
|---|---|
| P1 square | exact, case-insensitive (`white knight` / `empty`) |
| P2 legal moves | count exact (first integer); list F1 over SAN tokens (secondary) |
| P3 FEN after move | the first FEN-like token's piece-placement field |
| P4 in check | yes/no, the answer's first word |
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any

import chess

from ks.chess import parse as kp
from ks.data import primer
from ks.data.manifest import git_sha
from ks.eval import metrics as m
from ks.eval.backends import Backend, Request
from ks.eval.profile import Profile

FORMAT_HINT = {
    "P1": "Reply with only the colour and piece (e.g. `white knight`) or `empty`.",
    "P2": "Reply with only the count, a colon, then the moves in SAN separated by commas (e.g. `2: Ka1, Kb2`).",
    "P3": "Reply with only the full FEN of the new position.",
    "P4": "Reply with only `no`, or `yes, by` and the checking pieces (e.g. `yes, by Qe7`).",
}
_PLACEMENT = re.compile(r"([pnbrqkPNBRQK1-8]{1,8}(?:/[pnbrqkPNBRQK1-8]{1,8}){7})")
_INT = re.compile(r"\d+")
_SAN_TOKEN = re.compile(r"[A-Za-z0-9=+#-]+")


def messages(row: dict[str, Any]) -> list[dict[str, str]]:
    b = chess.Board(row["fen"])
    q = f"{row['question']}\n{FORMAT_HINT[row['task']]}"
    return [
        {"role": "system", "content": primer.SYSTEM},
        {"role": "user", "content": primer.user_prompt(b, q, legal=False)},
    ]


def extract(text: str) -> str:
    text = kp.cut(text)
    blocks = re.findall(r"<answer>(.*?)</answer>", text, re.DOTALL)
    if blocks:
        return blocks[-1].strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def _clean(s: str) -> str:
    return s.strip().strip("`*\"'.").strip().lower()


def _moves(s: str) -> set[str]:
    return {kp.normalise(t) for t in _SAN_TOKEN.findall(s)} - {""}


def grade(task: str, reference: str, reply: str) -> dict[str, float]:
    a = extract(reply)
    if task == "P1":
        return {"exact": float(_clean(a) == reference)}
    if task == "P2":
        ref_n, _, ref_list = reference.partition(":")
        got_n = _INT.search(a)
        exact = float(got_n is not None and int(got_n.group()) == int(ref_n))
        body = a.split(":", 1)[1] if ":" in a else a
        want, got = _moves(ref_list), _moves(body)
        tp = len(want & got)
        f1 = 0.0 if tp == 0 else 2 * tp / (len(want) + len(got))
        return {"exact": exact, "f1": f1}
    if task == "P3":
        got = _PLACEMENT.search(a)
        return {"exact": float(got is not None and got.group(1) == reference.split()[0])}
    if task == "P4":
        words = _clean(a).replace(",", " ").split()
        return {"exact": float(bool(words) and words[0] == reference.split(",")[0])}
    raise ValueError(task)


def run(profile: Profile, rows: list[dict[str, Any]], backend: Backend) -> dict[str, Any]:
    t0 = time.monotonic()
    started = datetime.now(UTC).replace(microsecond=0)
    reqs = [Request(r["id"], chess.Board(r["fen"]), messages(r)) for r in rows]
    outs = backend.generate(reqs, 1)
    items = []
    for r, o in zip(rows, outs, strict=True):
        c = o[0]
        items.append(
            {
                "id": r["id"],
                "task": r["task"],
                "answer": r["answer"],
                "text": c.text,
                "tokens_out": c.tokens_out,
                "finish": c.finish,
                **grade(r["task"], r["answer"], c.text),
            }
        )
    summary: dict[str, Any] = {}
    for task in FORMAT_HINT:
        sub = [it for it in items if it["task"] == task]
        if not sub:
            continue
        summary[task] = {"n": len(sub), "exact": m.mean_ci([it["exact"] for it in sub]).as_dict()}
        if task == "P2":
            summary[task]["f1"] = m.mean_ci([it["f1"] for it in sub]).as_dict()
    header = {
        "set": "probe500",
        "run": profile.name,
        "profile": profile.model_dump(),
        "checkpoint": None,
        "git_sha": git_sha(),
        "started": started.isoformat().replace("+00:00", "Z"),
        "seconds": round(time.monotonic() - t0, 1),
        "cost_usd": round(backend.cost_usd, 6),
    }
    return {"header": header, "summary": summary, "items": items}


def markdown(result: dict[str, Any]) -> str:
    h, s = result["header"], result["summary"]
    p = h["profile"]
    names = {
        "P1": "P1 square",
        "P2": "P2 legal count",
        "P3": "P3 FEN after move",
        "P4": "P4 in check",
    }
    lines = [
        f"# {h['run']} on probe500 (E0)",
        "",
        f"- model: `{p.get('hf_repo') or p.get('vertex_model') or p['backend']}`",
        f"- git `{h['git_sha']}`; {h['started']}, {h['seconds']:.0f} s, cost ${h['cost_usd']:.4f}",
        f"- decoding: T={p['temperature']}, max {p['max_tokens']} tokens, "
        f"chat template {p['chat_template_kwargs'] or 'default'}",
        "",
        "| Task | n | exact match |",
        "|---|---|---|",
    ]
    for task, d in s.items():
        e = d["exact"]
        row = f"| {names[task]} | {d['n']} | {100 * e['value']:.1f}% [{100 * e['lo']:.1f}, {100 * e['hi']:.1f}] |"
        lines.append(row)
    if "P2" in s:
        f = s["P2"]["f1"]
        lines += [
            "",
            f"P2 legal-move list F1: {100 * f['value']:.1f}% [{100 * f['lo']:.1f}, {100 * f['hi']:.1f}]",
        ]
    return "\n".join(lines) + "\n"
