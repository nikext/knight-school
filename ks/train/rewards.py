"""GRPO reward functions over `ks.chess.rewards` (TRAINING.md §3, §4).

TRL sums the weighted reward functions and logs each one as
`rewards/<name>/mean|std`. The task reward and `format` carry weight 1. The
other components (`legal`, and `sparse`/`dense` when they aren't the task) carry
weight 0: they're logged, not trained on. Each completion is parsed once per
step, and every function reads the same scores.

The task function also logs, through TRL's `log_metric`: the p95 completion
length, completion tokens, the share truncated at the token cap, and how much
prose comes before `<answer>`. The base model answers directly (ADR-017), so
that prose is the sign that RL grew reasoning. TRL's own `clipped_ratio` counts
every completion that doesn't end in EOS, so under a `</answer>` stop string
(ADR-022) it counts the stopped ones too.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from ks.chess import rewards as kr
from ks.chess.parse import STOP

Sink = Callable[[list[dict[str, Any]]], None]
COMPONENTS = ("sparse", "dense", "dense_norm", "legal")


def text_of(completion: Any) -> str:
    """Conversational datasets give [{"role": "assistant", "content": ...}]."""
    if isinstance(completion, list):
        return completion[-1]["content"]
    return completion


def prose_before_answer(text: str) -> int:
    """Characters of non-blank text before the first `<answer>` (all of it if there is none)."""
    i = text.find("<answer>")
    return len((text if i < 0 else text[:i]).strip())


def p95(values: Sequence[int | float]) -> float:
    return float(np.percentile(values, 95)) if len(values) else 0.0


class RewardFns:
    def __init__(
        self,
        task: kr.TaskReward,
        require_think: bool,
        sink: Sink | None = None,
        samples_per_step: int = 0,
        max_completion: int | None = None,
    ) -> None:
        self.task = task
        self.max_completion = max_completion
        self.require_think = require_think
        self.sink = sink
        self.samples_per_step = samples_per_step
        self._key: tuple[str, ...] | None = None
        self._scores: list[kr.Reward] = []

    def scores(self, completions: list[Any], **cols: Any) -> list[kr.Reward]:
        texts = [text_of(c) for c in completions]
        key = tuple(texts) + tuple(cols["fen"])
        if key != self._key:
            out = []
            for i, t in enumerate(texts):
                rec = {k: cols[k][i] for k in ("fen", "solution_uci", "is_last", "legal_san", "wp")}
                out.append(kr.score(t, kr.Target.from_record(rec), self.require_think))
            self._key, self._scores = key, out
        return self._scores

    def _component(self, name: str) -> Callable[..., list[float]]:
        def fn(completions: list[Any], **kw: Any) -> list[float]:
            vals = []
            for r in self.scores(completions, **kw):
                v = r.format if name == "format" else r.components().get(name)
                if v is None:
                    raise ValueError(f"{name} reward needs a reward table (rl_train has one)")
                vals.append(float(v))
            if name == self.task:
                self._log(completions, vals, **kw)
            return vals

        fn.__name__ = name
        return fn

    def funcs(self) -> tuple[list[Callable[..., list[float]]], list[float]]:
        """Reward functions and their weights: task and format train, the rest only log."""
        names = [self.task, "format"] + [c for c in COMPONENTS if c != self.task]
        weights = [1.0, 1.0] + [0.0] * (len(names) - 2)
        return [self._component(n) for n in names], weights

    def _log(self, completions: list[Any], task_vals: list[float], **kw: Any) -> None:
        texts = [text_of(c) for c in completions]
        log_metric = kw.get("log_metric")
        if log_metric is not None:
            lengths = [len(ids) for ids in kw.get("completion_ids") or []]
            prose = [prose_before_answer(t) for t in texts]
            log_metric("completions/p95_length", p95(lengths))
            log_metric("completions/tokens", float(sum(lengths)))
            if self.max_completion and lengths:
                cap = [
                    n >= self.max_completion and STOP not in t
                    for n, t in zip(lengths, texts, strict=True)
                ]
                log_metric("completions/truncated", float(np.mean(cap)))
            log_metric("reasoning/prose_frac", float(np.mean([p > 0 for p in prose])))
            log_metric("reasoning/prose_chars_mean", float(np.mean(prose)))
        if self.sink is None or not self.samples_per_step:
            return
        state = kw.get("trainer_state")
        step = (state.global_step + 1) if state is not None else None
        scores = self._scores
        rows = []
        for i in range(min(self.samples_per_step, len(texts))):
            rows.append(
                {
                    "step": step,
                    "fen": kw["fen"][i],
                    "solution_uci": kw["solution_uci"][i],
                    "text": texts[i],
                    "san": scores[i].parsed.san,
                    "status": scores[i].parsed.status,
                    "task": task_vals[i],
                    **scores[i].components(),
                }
            )
        self.sink(rows)
