"""GRPO reward functions: weights, one parse per completion, logged metrics, samples."""

from __future__ import annotations

from types import SimpleNamespace

import chess
import pytest

from ks.chess import board as kb
from ks.train import rewards as tr

FEN = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


def cols(n: int) -> dict:
    b = chess.Board(FEN)
    legal = sorted(b.san(m) for m in b.legal_moves)
    wp = [1.0 if s == "Qxf7#" else 0.2 for s in legal]
    return {
        "fen": [FEN] * n,
        "solution_uci": ["h5f7"] * n,
        "is_last": [True] * n,
        "legal_san": [legal] * n,
        "wp": [wp] * n,
    }


def comp(text: str) -> list[dict[str, str]]:
    return [{"role": "assistant", "content": text}]


def test_task_and_format_train_the_rest_only_log():
    fns, weights = tr.RewardFns("dense", require_think=False).funcs()
    names = [f.__name__ for f in fns]
    assert names[:2] == ["dense", "format"] and weights[:2] == [1.0, 1.0]
    assert set(names[2:]) == {"sparse", "dense_norm", "legal"} and set(weights[2:]) == {0.0}
    fns, _ = tr.RewardFns("sparse", require_think=False).funcs()
    assert [f.__name__ for f in fns][:2] == ["sparse", "format"]


def test_values_match_the_shared_reward():
    rf = tr.RewardFns("sparse", require_think=False)
    fns, _ = rf.funcs()
    by = {f.__name__: f for f in fns}
    completions = [
        comp("<answer>Qxf7#</answer>"),
        comp("<answer>Nc3</answer>"),
        comp("<answer>Ke3</answer>"),
    ]
    c = cols(3)
    assert by["sparse"](completions, **c) == [1.0, 0.0, 0.0]
    assert by["format"](completions, **c) == pytest.approx([0.1, 0.1, 0.1])
    assert by["legal"](completions, **c) == [1.0, 1.0, 0.0]  # Ke3 isn't legal here
    assert by["dense"](completions, **c) == [1.0, 0.2, 0.0]


def test_each_completion_is_parsed_once_per_batch(monkeypatch):
    calls = []
    real = tr.kr.score
    monkeypatch.setattr(tr.kr, "score", lambda *a, **k: calls.append(1) or real(*a, **k))
    rf = tr.RewardFns("dense", require_think=False)
    fns, _ = rf.funcs()
    completions, c = [comp("<answer>Qxf7#</answer>")] * 4, cols(4)
    for f in fns:
        f(completions, **c)
    assert len(calls) == 4


def test_task_function_logs_lengths_prose_and_samples():
    metrics: dict[str, float] = {}
    sunk: list[dict] = []
    rf = tr.RewardFns(
        "dense", require_think=False, sink=sunk.extend, samples_per_step=2, max_completion=1024
    )
    task = rf.funcs()[0][0]
    completions = [
        comp("The queen takes f7. <answer>Qxf7#</answer>"),
        comp("<answer>Nc3</answer>"),
        comp("hmm"),
        comp("<answer>Nc3</answer>" + " ramble" * 900),  # v2-style tail: answered, not truncated
    ]
    task(
        completions,
        completion_ids=[[0] * 12, [0] * 5, [0] * 1024, [0] * 1024],
        log_metric=metrics.__setitem__,
        trainer_state=SimpleNamespace(global_step=6),
        **cols(4),
    )
    assert metrics["completions/tokens"] == 12 + 5 + 1024 + 1024
    assert metrics["completions/p95_length"] > 900
    assert metrics["completions/truncated"] == pytest.approx(1 / 4)
    assert metrics["reasoning/prose_frac"] == pytest.approx(2 / 4)
    assert (
        len(sunk) == 2
        and sunk[0]["step"] == 7
        and sunk[0]["san"] == "Qxf7#"
        and sunk[0]["task"] == 1.0
    )


def test_prose_before_answer():
    assert tr.prose_before_answer("<answer>e4</answer>") == 0
    assert tr.prose_before_answer("  \n<answer>e4</answer>") == 0
    assert tr.prose_before_answer("e4 wins <answer>e4</answer>") == len("e4 wins")
    assert tr.prose_before_answer("no answer") == len("no answer")


def test_fixture_position_is_not_degenerate():
    assert kb.key(chess.Board(FEN))
