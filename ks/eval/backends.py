"""Eval backends (EVALS.md §3). Each turns prompts into completions and meters cost.

The engine baselines answer in the same `<answer>` format, so every backend's
output goes through the one parser and grader. The vLLM and Gemini backends
import their heavy libraries lazily; vLLM only exists in the container and in
the optional local `train` environment.
"""

from __future__ import annotations

import hashlib
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Protocol

import chess
import chess.engine

from ks.eval.profile import Profile


@dataclass
class Request:
    id: str
    board: chess.Board
    messages: list[dict[str, str]]


@dataclass
class Completion:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish: str = "stop"  # "stop" | "length"


class Backend(Protocol):
    @property
    def cost_usd(self) -> float: ...

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]: ...

    def close(self) -> None: ...


def answer(san: str) -> str:
    return f"<answer>{san}</answer>"


def _seed(seed: int, req_id: str, i: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{req_id}:{i}".encode()).digest()[:8], "big")


class RandomBackend:
    """A uniform random legal move, seeded per item (order-independent)."""

    def __init__(self, profile: Profile) -> None:
        self.seed = profile.seed
        self.cost_usd = 0.0

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]:
        out = []
        for r in reqs:
            moves = sorted(r.board.legal_moves, key=lambda m: m.uci())
            row = []
            for i in range(n):
                m = random.Random(_seed(self.seed, r.id, i)).choice(moves)
                row.append(Completion(answer(r.board.san(m))))
            out.append(row)
        return out

    def close(self) -> None:
        pass


class StockfishBackend:
    """Stockfish at a fixed node count, 1 thread, hash cleared per position (DATA.md §6)."""

    def __init__(self, profile: Profile) -> None:
        from ks.data.rewards import stockfish_path

        if not profile.nodes:
            raise ValueError("stockfish profile needs `nodes`")
        self.nodes = profile.nodes
        self.engine = chess.engine.SimpleEngine.popen_uci(stockfish_path())
        self.engine.configure({"Threads": 1, "Hash": 16})
        self.version = self.engine.id.get("name", "stockfish")
        self.cost_usd = 0.0

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]:
        if n != 1:
            raise ValueError("stockfish is deterministic; n must be 1")
        out = []
        for r in reqs:
            res = self.engine.play(r.board, chess.engine.Limit(nodes=self.nodes), game=object())
            assert res.move is not None
            out.append([Completion(answer(r.board.san(res.move)))])
        return out

    def close(self) -> None:
        self.engine.quit()


class VllmBackend:
    """Offline batch generation with vLLM. Cost = wall seconds x the machine's hourly price.

    The price comes from `KS_PRICE_PER_HOUR` (set by the eval job on a cloud VM);
    on the laptop it is 0.
    """

    def __init__(self, profile: Profile, model_path: str | None = None, seed: int = 0) -> None:
        from vllm import LLM  # type: ignore[import-not-found]

        self.profile = profile
        self.price_per_hour = float(os.environ.get("KS_PRICE_PER_HOUR", "0") or 0)
        kwargs: dict[str, Any] = {
            "model": model_path or profile.hf_repo,
            "dtype": profile.dtype,
            "max_model_len": profile.max_model_len,
            "gpu_memory_utilization": profile.gpu_memory_utilization,
            "enforce_eager": profile.enforce_eager,
            "seed": seed,
        }
        if model_path is None and profile.revision:
            kwargs["revision"] = profile.revision
        if profile.quantization:
            kwargs["quantization"] = profile.quantization
        if profile.language_model_only:
            kwargs["language_model_only"] = True
        t0 = time.monotonic()
        self.llm = LLM(**kwargs)
        self.load_seconds = time.monotonic() - t0
        self.gen_seconds = 0.0
        self.cost_usd = self.load_seconds * self.price_per_hour / 3600

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]:
        from vllm import SamplingParams  # type: ignore[import-not-found]

        p = self.profile
        sp = SamplingParams(
            n=n,
            temperature=p.temperature if n == 1 else 1.0,
            top_p=p.top_p,
            top_k=p.top_k,
            max_tokens=p.max_tokens,
            seed=p.seed,
        )
        t0 = time.monotonic()
        convs: Any = [r.messages for r in reqs]
        outs = self.llm.chat(
            convs,
            sp,
            use_tqdm=False,
            chat_template_kwargs=p.chat_template_kwargs or None,
        )
        dt = time.monotonic() - t0
        self.gen_seconds += dt
        self.cost_usd += dt * self.price_per_hour / 3600
        result = []
        for o in outs:
            n_in = len(o.prompt_token_ids or [])
            result.append(
                [
                    Completion(c.text, n_in, len(c.token_ids), c.finish_reason or "stop")
                    for c in o.outputs
                ]
            )
        return result

    def close(self) -> None:
        del self.llm


def make(profile: Profile, model_path: str | None = None) -> Backend:
    if profile.backend == "random":
        return RandomBackend(profile)
    if profile.backend == "stockfish":
        return StockfishBackend(profile)
    if profile.backend == "vllm":
        return VllmBackend(profile, model_path)
    if profile.backend == "gemini":
        from ks.eval.gemini import GeminiBackend

        return GeminiBackend(profile)
    raise ValueError(profile.backend)
