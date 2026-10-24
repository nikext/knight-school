"""Primer SFT data (TRAINING.md §5, ADR-023): chats -> token ids with answer-only labels, and
the order the trainer reads them in.

Each example is the prompt rendered by the chat template with a generation prompt (exactly the
token ids vLLM sees at inference), followed by the answer and the end-of-turn token. Labels are
-100 on the prompt, so the loss is on the answer and the end of turn only. The template's
trailing newline after the end of turn is dropped: generation stops before it.

Order: no packing (ADR-023). The examples are shuffled once, cut into optimizer steps of
`step_examples`, and sorted by length inside each step, longest first. Every step is a random
sample of the primer, and each micro-batch pads to a similar length. The trainer then reads the
dataset sequentially, so a resume skips to the same place.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

import numpy as np

IGNORE = -100


class Tokenizer(Protocol):
    def apply_chat_template(self, conversation: Any, **kw: Any) -> Any: ...

    def __call__(self, text: list[str], **kw: Any) -> Any: ...


def end_of_turn(tok: Tokenizer, example: dict[str, Any], template_kwargs: dict[str, Any]) -> str:
    """What the template writes after an assistant answer, minus trailing whitespace."""
    msgs = example["messages"]
    full = tok.apply_chat_template(msgs, tokenize=False, **template_kwargs)
    prompt = tok.apply_chat_template(
        msgs[:-1], tokenize=False, add_generation_prompt=True, **template_kwargs
    )
    answer = msgs[-1]["content"]
    if not full.startswith(prompt) or not full[len(prompt) :].startswith(answer):
        raise ValueError("chat template doesn't render prompt + answer as a prefix of the chat")
    end = full[len(prompt) + len(answer) :].rstrip()
    if not end:
        raise ValueError("chat template writes no end-of-turn token after the answer")
    return end


def tokenize(
    tok: Tokenizer,
    examples: Sequence[dict[str, Any]],
    template_kwargs: dict[str, Any],
    end: str,
) -> dict[str, list[Any]]:
    prompts = [
        tok.apply_chat_template(
            e["messages"][:-1], tokenize=False, add_generation_prompt=True, **template_kwargs
        )
        for e in examples
    ]
    answers = [e["messages"][-1]["content"] + end for e in examples]
    p_ids = tok(prompts, add_special_tokens=False)["input_ids"]
    a_ids = tok(answers, add_special_tokens=False)["input_ids"]
    input_ids = [list(p) + list(a) for p, a in zip(p_ids, a_ids, strict=True)]
    labels = [[IGNORE] * len(p) + list(a) for p, a in zip(p_ids, a_ids, strict=True)]
    return {
        "input_ids": input_ids,
        "labels": labels,
        "length": [len(x) for x in input_ids],
        "task": [e["task"] for e in examples],
    }


def step_order(lengths: Sequence[int], step_examples: int, seed: int) -> list[int]:
    """Indices: shuffled, then sorted longest-first inside each block of `step_examples`."""
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(lengths))
    lens = np.asarray(lengths)
    out: list[int] = []
    for i in range(0, len(perm), step_examples):
        block = perm[i : i + step_examples]
        out += block[np.argsort(-lens[block], kind="stable")].tolist()
    return out


def contamination_hits(examples: Iterable[dict[str, Any]], blocked: frozenset[str]) -> int:
    """Examples showing a blocklisted position (their `keys`, DATA.md §5)."""
    return sum(any(k in blocked for k in e.get("keys", ())) for e in examples)


def summary(lengths: Sequence[int], labels: Sequence[Sequence[int]], tasks: Sequence[str]) -> dict:
    n_loss = [sum(t != IGNORE for t in lb) for lb in labels]
    return {
        "examples": len(lengths),
        "tokens": int(sum(lengths)),
        "loss_tokens": int(sum(n_loss)),
        "length_max": int(max(lengths, default=0)),
        "per_task": dict(sorted(Counter(tasks).items())),
    }
