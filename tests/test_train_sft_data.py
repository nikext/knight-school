"""Primer SFT data: answer-only labels, the template's end of turn, step order, contamination."""

from __future__ import annotations

from typing import Any

import pytest

from ks.train import sft_data as sd


class CharTok:
    """A ChatML-ish template and a tokenizer with one id per character."""

    def apply_chat_template(
        self,
        conversation: list[dict[str, str]],
        tokenize: bool = False,
        add_generation_prompt: bool = False,
        **kw: Any,
    ) -> str:
        s = "".join(f"<{m['role']}>{m['content']}|" for m in conversation)
        return s + "<assistant>" if add_generation_prompt else s + "\n"

    def __call__(self, text: list[str], **kw: Any) -> dict[str, list[list[int]]]:
        return {"input_ids": [[ord(c) for c in t] for t in text]}


def ex(answer: str, task: str = "T5", keys: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "task": task,
        "keys": list(keys),
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": answer},
        ],
    }


def test_labels_cover_the_answer_and_end_of_turn_only():
    tok = CharTok()
    end = sd.end_of_turn(tok, ex("Nf3"), {})
    assert end == "|"  # the trailing newline after the end of turn is dropped
    out = sd.tokenize(tok, [ex("Nf3"), ex("white knight", "T1")], {}, end)
    ids, labels = out["input_ids"][0], out["labels"][0]
    prompt = "<system>sys|<user>q|<assistant>"
    assert "".join(chr(i) for i in ids) == prompt + "Nf3|"
    assert labels[: len(prompt)] == [sd.IGNORE] * len(prompt)
    assert "".join(chr(t) for t in labels[len(prompt) :]) == "Nf3|"
    assert out["length"] == [len(prompt) + 4, len(prompt) + 13]
    assert out["task"] == ["T5", "T1"]
    s = sd.summary(out["length"], out["labels"], out["task"])
    assert s["loss_tokens"] == 4 + 13 and s["per_task"] == {"T1": 1, "T5": 1}


def test_a_template_that_rewrites_the_answer_is_refused():
    class Bad(CharTok):
        def apply_chat_template(
            self,
            conversation: list[dict[str, str]],
            tokenize: bool = False,
            add_generation_prompt: bool = False,
            **kw: Any,
        ) -> str:
            s = super().apply_chat_template(conversation, tokenize, add_generation_prompt)
            return s.replace("Nf3", "<think></think>Nf3")

    with pytest.raises(ValueError, match="prefix"):
        sd.end_of_turn(Bad(), ex("Nf3"), {})


def test_steps_are_random_samples_sorted_inside():
    lengths = [i % 7 + 1 for i in range(100)]
    order = sd.step_order(lengths, 16, seed=2026)
    assert sorted(order) == list(range(100))
    blocks = [order[i : i + 16] for i in range(0, 100, 16)]
    for b in blocks:
        assert [lengths[i] for i in b] == sorted((lengths[i] for i in b), reverse=True)
    assert order == sd.step_order(lengths, 16, seed=2026)
    assert order != sd.step_order(lengths, 16, seed=7)
    assert blocks[0] != sorted(blocks[0])  # shuffled, not index order


def test_contamination_hits_read_the_keys():
    blocked = frozenset({"8/8/8/8/8/8/8/K6k w - -"})
    exs = [ex("Kb1", keys=("8/8/8/8/8/8/8/K6k w - -",)), ex("e4", keys=("x",)), ex("d4")]
    assert sd.contamination_hits(exs, blocked) == 1
