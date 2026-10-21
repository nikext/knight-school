"""Exact primer token counts with the chosen model's tokenizer (DATA.md §7, task M2 §7).

Each example is rendered with the model's chat template (and the profile's
template switches), exactly as SFT will see it, then tokenized. Counts per
task: all tokens, and answer tokens (the loss tokens: the full sequence minus
the prompt rendered with a generation prompt). The result goes into the
`tokens` field of manifests/primer_{S,M}.json; nothing else in them changes.

    ks primer-tokens qwen3-1.7b
"""

from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from ks.data import manifest
from ks.data.primer import read_shards
from ks.eval import profile as prof

BATCH = 512


def _count_shard(args: tuple[str, str, str | None, dict[str, Any]]) -> dict[str, Counter]:
    path, repo, revision, kwargs = args
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    tok = AutoTokenizer.from_pretrained(repo, revision=revision)
    total: Counter = Counter()
    answer: Counter = Counter()
    n: Counter = Counter()
    batch: list[dict[str, Any]] = []

    def flush() -> None:
        full = [tok.apply_chat_template(e["messages"], tokenize=False, **kwargs) for e in batch]
        prompt = [
            tok.apply_chat_template(
                e["messages"][:-1], tokenize=False, add_generation_prompt=True, **kwargs
            )
            for e in batch
        ]
        lf = tok(full, add_special_tokens=False)["input_ids"]
        lp = tok(prompt, add_special_tokens=False)["input_ids"]
        for e, a, b in zip(batch, lf, lp, strict=True):
            total[e["task"]] += len(a)
            answer[e["task"]] += len(a) - len(b)
            n[e["task"]] += 1
        batch.clear()

    for ex in read_shards([Path(path)]):
        batch.append(ex)
        if len(batch) >= BATCH:
            flush()
    if batch:
        flush()
    return {"total": total, "answer": answer, "n": n}


def count(model: str, sets: tuple[str, ...] = ("S", "M"), workers: int = 16) -> dict[str, Any]:
    p = prof.load(model)
    assert p.hf_repo, "token counts need an open model's tokenizer"
    out: dict[str, Any] = {}
    for name in sets:
        shards = sorted(Path(manifest.DATA / "primer" / name).glob("shard-*.jsonl.zst"))
        if not shards:
            raise FileNotFoundError(f"no primer {name} shards; run `make data` first")
        jobs = [(str(s), p.hf_repo, p.revision, p.chat_template_kwargs) for s in shards]
        total: Counter = Counter()
        answer: Counter = Counter()
        n: Counter = Counter()
        with ProcessPoolExecutor(min(workers, len(jobs))) as ex:
            for r in ex.map(_count_shard, jobs):
                total.update(r["total"])
                answer.update(r["answer"])
                n.update(r["n"])
        out[name] = {
            "tokenizer": f"{p.hf_repo}@{(p.revision or '')[:12]}",
            "chat_template_kwargs": p.chat_template_kwargs,
            "total": sum(total.values()),
            "answer": sum(answer.values()),
            "examples": sum(n.values()),
            "per_task": {
                t: {"examples": n[t], "total": total[t], "answer": answer[t]} for t in sorted(n)
            },
        }
    return out


def write_manifests(counts: dict[str, Any]) -> None:
    for name, c in counts.items():
        path = manifest.manifest_path(f"primer_{name}")
        doc = json.loads(path.read_text())
        doc["tokens"] = c
        path.write_text(json.dumps(doc, indent=2) + "\n")
