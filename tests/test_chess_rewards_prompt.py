from __future__ import annotations

import chess
import pytest

from ks.chess import prompt as kpr
from ks.chess import rewards as kr

# White mates with either rook: Ra8# (the listed solution) or Rd8#.
TWO_MATES = "6k1/5ppp/8/8/8/8/5PPP/R2R2K1 w - - 0 1"


def target(is_last: bool = True, with_table: bool = True) -> kr.Target:
    b = chess.Board(TWO_MATES)
    legal = sorted(b.san(m) for m in b.legal_moves)
    wp = {s: (1.0 if s.endswith("#") else 0.5) for s in legal} if with_table else None
    if wp is not None:
        wp["h3"] = 0.25
    return kr.Target(b, chess.Move.from_uci("a1a8"), is_last, wp)


def test_solution_scores_everything():
    r = kr.score("<think>x</think><answer>Ra8#</answer>", target())
    assert (r.format, r.sparse, r.dense, r.dense_norm) == (0.1, 1.0, 1.0, 1.0)
    assert r.total("sparse") == pytest.approx(1.1)
    assert r.components() == {
        "format": 0.1,
        "sparse": 1.0,
        "legal": 1.0,
        "dense": 1.0,
        "dense_norm": 1.0,
    }


def test_other_mate_counts_only_on_the_last_move():
    assert kr.score("<think>x</think><answer>Rd8</answer>", target(is_last=True)).sparse == 1.0
    assert kr.score("<think>x</think><answer>Rd8</answer>", target(is_last=False)).sparse == 0.0


def test_dense_and_norm():
    r = kr.score("<think>x</think><answer>h3</answer>", target())
    assert r.sparse == 0.0 and r.dense == 0.25 and r.dense_norm == 0.0
    r = kr.score("<think>x</think><answer>Kf1</answer>", target())
    assert r.dense == 0.5 and r.dense_norm == pytest.approx(1 / 3)
    assert r.total("dense") == pytest.approx(0.6)


def test_illegal_gets_zero_task_reward_but_keeps_format():
    r = kr.score("<think>x</think><answer>Qh5</answer>", target())
    assert (r.format, r.sparse, r.dense, r.dense_norm) == (0.1, 0.0, 0.0, 0.0)
    r = kr.score("no tags at all", target())
    assert (r.format, r.sparse, r.dense) == (0.0, 0.0, 0.0)


def test_format_needs_think_unless_told_otherwise():
    text = "<answer>Ra8#</answer>"
    assert kr.score(text, target()).format == 0.0
    assert kr.score(text, target(), require_think=False).format == 0.1


def test_dense_without_table_raises():
    r = kr.score("<think>x</think><answer>Ra8#</answer>", target(with_table=False))
    assert r.dense is None and "dense" not in r.components()
    with pytest.raises(ValueError):
        r.total("dense")


def test_target_from_record():
    b = chess.Board(TWO_MATES)
    legal = sorted(b.san(m) for m in b.legal_moves)
    rec = {
        "fen": TWO_MATES,
        "solution_uci": "a1a8",
        "is_last": True,
        "legal_san": legal,
        "wp": [0.3] * len(legal),
    }
    t = kr.Target.from_record(rec)
    assert t.wp is not None and t.wp["Ra8#"] == 0.3 and t.is_last
    assert kr.Target.from_record({**rec, "wp": None}).wp is None


def test_prompt_text_and_hash():
    b = chess.Board()
    text = kpr.user_text(b)
    assert text.splitlines()[0] == f"Position (FEN): {b.fen()}"
    assert text.splitlines()[1] == "Side to move: White"
    assert text.splitlines()[2].startswith("Legal moves: Na3, Nc3, Nf3, Nh3, a3")
    assert "<think></think>" in text and "<answer></answer>" in text
    assert "<think>" not in kpr.user_text(b, think="native")
    assert "Legal moves" not in kpr.user_text(b, legal=False)
    msgs = kpr.messages(b)
    assert msgs[0] == {"role": "system", "content": kpr.SYSTEM}
    hashes = {kpr.prompt_hash(t, legal) for t in ("tags", "native") for legal in (True, False)}
    assert len(hashes) == 4


def test_prompt_hash_is_frozen():
    # Changing the prompt changes every result; update this only with an ADR.
    assert kpr.prompt_hash() == "c728de49e119"
    assert kpr.prompt_hash("native") == "b371401fde1c"
