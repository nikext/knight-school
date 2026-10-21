"""Gemini backend and cost meter, with recorded responses only (no live calls in M2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import chess
import pytest

from ks.chess import prompt as kpr
from ks.cloud.config import load_prices
from ks.eval import gemini as g
from ks.eval.backends import Request
from ks.eval.profile import Profile, load
from tests import factories as f

PROFILE = Profile(
    name="gem", backend="gemini", vertex_model="gemini-2.5-flash-lite", max_tokens=1000
)
AFTER = datetime(2026, 11, 14, 12, tzinfo=UTC)  # the vertex pool is usable from 2026-11-13
PRICE = g.Price(0.10, 0.40)


def caps_after():
    c = f.caps()
    v = c.pools["vertex"]
    c.pools["vertex"] = v.model_copy(update={"checked_on": AFTER - timedelta(days=1)})
    return c


def recorded(text: str, tin: int = 400, tout: int = 30, think: int = 0, finish: str = "STOP"):
    """Shaped like google.genai's GenerateContentResponse."""
    usage = SimpleNamespace(
        prompt_token_count=tin, candidates_token_count=tout, thoughts_token_count=think
    )
    cand = SimpleNamespace(finish_reason=f"FinishReason.{finish}")
    return SimpleNamespace(text=text, usage_metadata=usage, candidates=[cand])


class FakeModels:
    def __init__(self, responses: list[Any]) -> None:
        self.responses, self.calls = list(responses), []

    def generate_content(self, model: str, contents: Any, config: dict[str, Any]) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.responses.pop(0)


def req(i: int = 0) -> Request:
    b = chess.Board()
    return Request(f"p{i}-1", b, kpr.messages(b))


def backend(responses, allowed=1.0):
    client = SimpleNamespace(models=FakeModels(responses))
    return g.GeminiBackend(PROFILE, client=client, meter=g.Meter(allowed, PRICE)), client.models


def test_locked_before_usable_from():
    before = datetime(2026, 11, 12, 12, tzinfo=UTC)
    with pytest.raises(g.GeminiRefused, match="locked until 2026-11-13"):
        g.allowance(f.caps(), f.ledger(), "M2", 5.0, before)


def test_allowance_is_the_smallest_limit():
    assert g.allowance(caps_after(), f.ledger(), "M2", 5.0, AFTER) == 5.0
    assert g.allowance(caps_after(), f.ledger(), "M2", 500.0, AFTER) == pytest.approx(50.0)
    spent = f.ledger(f.charge("m2-gemini-x", 48.0, pool="vertex", milestone="M2", ts=AFTER))
    assert g.allowance(caps_after(), spent, "M2", 5.0, AFTER) == pytest.approx(2.0)
    gone = f.ledger(f.charge("m2-gemini-x", 50.0, pool="vertex", milestone="M2", ts=AFTER))
    with pytest.raises(g.GeminiRefused, match="M2 allocation"):
        g.allowance(caps_after(), gone, "M2", 5.0, AFTER)


def test_stale_credit_reading_refuses():
    c = f.caps()
    with pytest.raises(g.GeminiRefused, match="stale"):
        g.allowance(c, f.ledger(), "M2", 5.0, AFTER + timedelta(days=30))


def test_unverified_prices_refuse_but_can_be_read():
    prices = load_prices()
    with pytest.raises(g.GeminiRefused, match="not verified"):
        g.price_for(prices, "gemini-2.5-flash")
    p = g.price_for(prices, "gemini-2.5-flash", allow_unverified=True)
    b = g.price_for(prices, "gemini-2.5-flash", batch=True, allow_unverified=True)
    assert (b.input, b.output) == (p.input / 2, p.output / 2)
    with pytest.raises(g.GeminiRefused, match="no price"):
        g.price_for(prices, "gemini-9-ultra", allow_unverified=True)


def test_calls_are_booked_from_usage_metadata():
    be, models = backend([recorded("<think>x</think><answer>e4</answer>", 400, 30, think=70)])
    out = be.generate([req()])
    c = out[0][0]
    assert (c.text, c.tokens_in, c.tokens_out, c.finish) == (
        "<think>x</think><answer>e4</answer>",
        400,
        100,
        "stop",
    )
    assert be.cost_usd == pytest.approx((400 * 0.10 + 100 * 0.40) / 1e6)
    call = models.calls[0]
    assert call["model"] == "gemini-2.5-flash-lite"
    assert call["config"]["system_instruction"] == kpr.SYSTEM
    assert call["config"]["max_output_tokens"] == 1000
    assert "temperature" not in call["config"]  # provider default sampling
    assert call["contents"][0].startswith("Position (FEN):")


def test_max_tokens_finish_is_length():
    be, _ = backend([recorded("<think>long", finish="MAX_TOKENS")])
    assert be.generate([req()])[0][0].finish == "length"


def test_meter_refuses_before_a_call_could_break_the_cap():
    be, models = backend([recorded("<answer>e4</answer>")] * 5)
    worst = be._worst(req())
    be.meter.allowed_usd = worst * 1.0001  # room for one worst case, not one more after it
    with pytest.raises(g.GeminiRefused, match="next call could cost"):
        be.generate([req(i) for i in range(5)])
    assert len(models.calls) == 1
    assert be.cost_usd < worst


def test_thinking_budget_goes_into_the_config():
    p = PROFILE.model_copy(update={"thinking_budget": 0})
    assert g.gen_config(p, "s")["thinking_config"] == {"thinking_budget": 0}


def test_ledger_charge(tmp_path: Path, monkeypatch):
    events = []
    monkeypatch.setattr(g, "append_event", events.append)
    be, _ = backend([recorded("<answer>e4</answer>")])
    assert be.ledger_charge("m2-gemini-x") is None  # nothing spent, nothing booked
    be.generate([req()])
    ev = be.ledger_charge("m2-gemini-x")
    assert ev is not None and events == [ev]
    d = ev.model_dump()
    assert d["pool"] == "vertex" and d["kind"] == "gemini-online" and d["calls"] == 1
    assert d["tokens_in"] == 400 and d["actual_usd"] > 0


def test_needs_max_usd_without_a_meter():
    with pytest.raises(g.GeminiRefused, match="--max-usd"):
        g.GeminiBackend(PROFILE, client=SimpleNamespace(models=None))


def test_batch_jsonl_roundtrip():
    p = PROFILE.model_copy(update={"thinking_budget": 512})
    lines = g.batch_requests(p, [req(0), req(1)])
    first = json.loads(lines[0])
    assert first["key"] == "p0-1"
    body = first["request"]
    assert body["systemInstruction"]["parts"][0]["text"] == kpr.SYSTEM
    assert body["generationConfig"] == {
        "maxOutputTokens": 1000,
        "thinkingConfig": {"thinkingBudget": 512},
    }
    out_lines = [
        json.dumps(
            {
                "key": "p0-1",
                "response": {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "secret thoughts", "thought": True},
                                    {"text": "<answer>e4</answer>"},
                                ]
                            },
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 300,
                        "candidatesTokenCount": 10,
                        "thoughtsTokenCount": 90,
                    },
                },
            }
        ),
        json.dumps({"key": "p1-1", "response": {"candidates": [{"finishReason": "MAX_TOKENS"}]}}),
    ]
    comps, usd = g.parse_batch_output(out_lines, g.Price(0.05, 0.20))
    assert comps["p0-1"].text == "<answer>e4</answer>" and comps["p0-1"].tokens_out == 100
    assert comps["p1-1"].finish == "length" and comps["p1-1"].text == ""
    assert usd == pytest.approx((300 * 0.05 + 100 * 0.20) / 1e6)


def test_gemini_profiles_have_prices():
    prices = load_prices()
    for name in ("gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"):
        prof = load(name)
        assert prof.vertex_model is not None
        assert g.price_for(prices, prof.vertex_model, allow_unverified=True).output > 0
