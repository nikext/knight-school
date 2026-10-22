"""Gemini baseline backend (EVALS.md §3) and its cost meter (BUDGET.md §6).

Built and unit-tested in M2, **run only from 2026-11-13** (ADR-013): the meter
refuses every call before the vertex pool's `usable_from`.

The meter's allowance for a run is the smallest of: the run's `--max-usd`, the
milestone's vertex allocation left, the pool ceiling left, and 90% of the
credit reading minus our spend since it. Before each call it reserves the
call's worst case (prompt tokens + max output + thinking budget, at the output
price); after the call it books the real cost from `usage_metadata`. A run
that ends (or stops at the cap) appends one ledger `charge`.

Full sets go through **batch** prediction (50% off). `batch_requests` and
`parse_batch_output` build and read the JSONL; submission itself is a
session-time step after the pilot (task file M2 §9) and is not exercised here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ks.cloud import config as cfg
from ks.cloud.ledger import ChargeEvent, LedgerState, append_event, load_state, now_ts
from ks.eval.backends import Completion, Request
from ks.eval.profile import Profile

POOL = "vertex"
CHARS_PER_TOKEN = 3.0  # conservative prompt-size estimate before the call (FEN text is dense)


class GeminiRefused(RuntimeError):
    pass


@dataclass(frozen=True)
class Price:
    input: float  # USD per 1M tokens
    output: float

    def usd(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * self.input + tokens_out * self.output) / 1e6


def price_for(
    prices: cfg.Prices, model: str, batch: bool = False, allow_unverified: bool = False
) -> Price:
    g = prices.gemini or {}
    if not g.get("verified") and not allow_unverified:
        raise GeminiRefused("prices.yaml gemini prices are not verified; re-read them first")
    row = (g.get("models") or {}).get(model)
    if row is None:
        raise GeminiRefused(f"no price for {model!r} in prices.yaml")
    if batch:
        return Price(row["batch_input"], row["batch_output"])
    return Price(row["input"], row["output"])


def allowance(
    caps: cfg.Caps, ledger: LedgerState, milestone: str, max_usd: float, now: datetime
) -> float:
    """The most this run may spend, or GeminiRefused with the reason."""
    pool = caps.pools[POOL]
    lim = caps.limits
    if (start := pool.usable_from_at()) and now < start:
        raise GeminiRefused(f"vertex pool is locked until {pool.usable_from} (ADR-013)")
    if (end := pool.expires_at()) and now > end - timedelta(hours=lim.expiry_margin_hours):
        raise GeminiRefused(f"vertex credit expires {pool.expires}")
    if pool.remaining_usd is None or pool.checked_on is None:
        raise GeminiRefused("no vertex credit reading in caps.yaml")
    if now - pool.checked_on > timedelta(days=lim.credit_check_max_age_days):
        raise GeminiRefused("vertex credit reading is stale; re-read Billing -> Credits")
    alloc = caps.allocations[POOL].get(milestone)
    if alloc is None:
        raise GeminiRefused(f"no vertex allocation for {milestone}")
    running = ledger.running(POOL)
    left = {
        "--max-usd": max_usd,
        f"{milestone} allocation": alloc
        - ledger.spent(POOL, milestone)
        - ledger.running(POOL, milestone),
        "pool ceiling": pool.ceiling - ledger.spent(POOL) - running,
        "credit headroom": lim.credit_reserve_factor * pool.remaining_usd
        - ledger.spent(POOL, since=pool.checked_on)
        - running,
    }
    name, value = min(left.items(), key=lambda kv: kv[1])
    if value <= 0:
        raise GeminiRefused(f"nothing left: {name} is ${value:.2f}")
    return value


@dataclass
class Meter:
    allowed_usd: float
    price: Price
    spent_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    log: list[str] = field(default_factory=list)

    def reserve(self, worst_usd: float) -> None:
        if self.spent_usd + worst_usd > self.allowed_usd:
            raise GeminiRefused(
                f"next call could cost ${worst_usd:.4f}; spent ${self.spent_usd:.4f} of ${self.allowed_usd:.4f}"
            )

    def book(self, tokens_in: int, tokens_out: int) -> float:
        usd = self.price.usd(tokens_in, tokens_out)
        self.spent_usd += usd
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.calls += 1
        return usd


def _usage(resp: Any) -> tuple[int, int]:
    u = resp.usage_metadata
    tin = int(getattr(u, "prompt_token_count", 0) or 0)
    out = int(getattr(u, "candidates_token_count", 0) or 0)
    think = int(getattr(u, "thoughts_token_count", 0) or 0)
    return tin, out + think


def _finish(resp: Any) -> str:
    try:
        reason = str(resp.candidates[0].finish_reason)
    except (AttributeError, IndexError, TypeError):
        return "stop"
    return "length" if "MAX_TOKENS" in reason else "stop"


def gen_config(profile: Profile, system: str) -> dict[str, Any]:
    conf: dict[str, Any] = {"system_instruction": system, "max_output_tokens": profile.max_tokens}
    if profile.temperature > 0:
        conf["temperature"] = profile.temperature
    if profile.thinking_budget is not None:
        conf["thinking_config"] = {"thinking_budget": profile.thinking_budget}
    return conf


class GeminiBackend:
    """Online calls (pilot runs). Every call is reserved and booked by the meter."""

    def __init__(
        self,
        profile: Profile,
        client: Any = None,  # google.genai.Client; tests pass a recorded fake
        meter: Meter | None = None,
        milestone: str = "M2",
        max_usd: float | None = None,
        now: datetime | None = None,
    ) -> None:
        if not profile.vertex_model:
            raise ValueError("gemini profile needs vertex_model")
        self.profile = profile
        if meter is None:
            if max_usd is None:
                raise GeminiRefused("a Gemini run needs --max-usd")
            prices = cfg.load_prices()
            price = price_for(prices, profile.vertex_model)
            limit = allowance(
                cfg.load_caps(), load_state(), milestone, max_usd, now or cfg.utcnow()
            )
            meter = Meter(limit, price)
        self.meter = meter
        self.milestone = milestone
        if client is None:
            from google import genai  # type: ignore[import-not-found]

            env = cfg.read_env()
            client = genai.Client(
                vertexai=True, project=env["GOOGLE_CLOUD_PROJECT"], location="global"
            )
        self.client = client

    @property
    def cost_usd(self) -> float:
        return self.meter.spent_usd

    def _worst(self, req: Request) -> float:
        chars = sum(len(m["content"]) for m in req.messages)
        out = self.profile.max_tokens + (self.profile.thinking_budget or 0)
        return self.meter.price.usd(int(chars / CHARS_PER_TOKEN) + 50, out)

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]:
        if n != 1:
            raise ValueError("Gemini evals take one sample per prompt")
        out = []
        for r in reqs:
            self.meter.reserve(self._worst(r))
            system = next(m["content"] for m in r.messages if m["role"] == "system")
            user = [m["content"] for m in r.messages if m["role"] == "user"]
            resp = self.client.models.generate_content(
                model=self.profile.vertex_model,
                contents=user,
                config=gen_config(self.profile, system),
            )
            tin, tout = _usage(resp)
            self.meter.book(tin, tout)
            out.append([Completion(resp.text or "", tin, tout, _finish(resp))])
        return out

    def close(self) -> None:
        pass

    def ledger_charge(self, run_id: str) -> ChargeEvent | None:
        if self.meter.calls == 0:
            return None
        ev = ChargeEvent.model_validate(
            {
                "ts": now_ts(),
                "id": run_id,
                "milestone": self.milestone,
                "pool": POOL,
                "kind": "gemini-online",
                "actual_usd": round(self.meter.spent_usd, 6),
                "tokens_in": self.meter.tokens_in,
                "tokens_out": self.meter.tokens_out,
                "calls": self.meter.calls,
            }
        )
        append_event(ev)
        return ev


# --- batch prediction ---------------------------------------------------------------


def batch_requests(profile: Profile, reqs: list[Request]) -> list[str]:
    """JSONL lines for Vertex batch prediction; `key` carries our item id."""
    lines = []
    for r in reqs:
        system = next(m["content"] for m in r.messages if m["role"] == "system")
        user = "\n".join(m["content"] for m in r.messages if m["role"] == "user")
        conf = gen_config(profile, system)
        sys_inst = conf.pop("system_instruction")
        thinking = conf.pop("thinking_config", None)
        gc: dict[str, Any] = {"maxOutputTokens": conf["max_output_tokens"]}
        if "temperature" in conf:
            gc["temperature"] = conf["temperature"]
        if thinking is not None:
            gc["thinkingConfig"] = {"thinkingBudget": thinking["thinking_budget"]}
        body = {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "systemInstruction": {"parts": [{"text": sys_inst}]},
            "generationConfig": gc,
        }
        lines.append(json.dumps({"key": r.id, "request": body}, ensure_ascii=False))
    return lines


def parse_batch_output(lines: list[str], price: Price) -> tuple[dict[str, Completion], float]:
    """Batch output JSONL -> completions by key, and the total cost at batch prices."""
    out: dict[str, Completion] = {}
    total = 0.0
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        resp = row.get("response") or {}
        cand = (resp.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        u = resp.get("usageMetadata") or {}
        tin = int(u.get("promptTokenCount", 0))
        tout = int(u.get("candidatesTokenCount", 0)) + int(u.get("thoughtsTokenCount", 0))
        total += price.usd(tin, tout)
        finish = "length" if cand.get("finishReason") == "MAX_TOKENS" else "stop"
        out[row["key"]] = Completion(text, tin, tout, finish)
    return out, total
