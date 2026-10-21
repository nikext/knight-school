"""M0 Vertex smoke: one tiny Gemini call with ADC, booked as a ledger charge.

    uv run --extra gemini python infra/vertex_smoke.py

This is the only Vertex spend before 2026-11-13 (ADR-013). The real cost
meter with prices.yaml arrives with the eval harness in M2.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from ks.cloud.config import read_env
from ks.cloud.ledger import ChargeEvent, append_event, now_ts

MODEL = "gemini-2.5-flash-lite"
# Catalog API, Vertex AI service C7E2-9256-1C43, fetched 2026-10-21:
#   F91E-007E-3BA1 "Gemini 2.5 Flash Lite Text Input - Predictions"  $1e-7 / token
#   2D6E-6AC5-B1FD "Gemini 2.5 Flash Lite Text Output - Predictions" $4e-7 / token
USD_PER_INPUT_TOKEN = 1e-7
USD_PER_OUTPUT_TOKEN = 4e-7


def main() -> None:
    env = read_env()
    client = genai.Client(
        vertexai=True, project=env["GOOGLE_CLOUD_PROJECT"], location="us-central1"
    )
    resp = client.models.generate_content(
        model=MODEL,
        contents="Reply with the single word: ready",
        config=types.GenerateContentConfig(
            max_output_tokens=8,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    usage = resp.usage_metadata
    assert usage is not None, "no usage_metadata in the response"
    tokens_in = usage.prompt_token_count or 0
    tokens_out = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    usd = tokens_in * USD_PER_INPUT_TOKEN + tokens_out * USD_PER_OUTPUT_TOKEN
    print(f"{MODEL}: {resp.text!r}  tokens in={tokens_in} out={tokens_out}  cost=${usd:.8f}")
    append_event(
        ChargeEvent.model_validate(
            {
                "ts": now_ts(),
                "id": "m0-vertex-smoke",
                "milestone": "M0",
                "pool": "vertex",
                "kind": "gemini-online",
                "actual_usd": round(usd, 8),
                "model": MODEL,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }
        )
    )
    print("ledger: charge m0-vertex-smoke booked to vertex/M0")


if __name__ == "__main__":
    main()
