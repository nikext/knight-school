"""Model profiles (`configs/models/*.yaml`, EVALS.md §3). No model ids in code."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from ks.chess.prompt import Think
from ks.cloud.config import REPO

MODELS_DIR = REPO / "configs" / "models"


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    backend: Literal["vllm", "gemini", "stockfish", "random"]
    description: str = ""
    license: str = ""

    # vllm
    hf_repo: str | None = None
    revision: str | None = None  # pinned commit sha
    language_model_only: bool = False  # skip a VLM's vision tower (vLLM)
    dtype: str = "bfloat16"
    quantization: str | None = None  # screening on the laptop only, never headline numbers
    max_model_len: int = 4096
    gpu_memory_utilization: float = 0.85
    enforce_eager: bool = False
    chat_template_kwargs: dict[str, Any] = Field(default_factory=dict)

    # gemini
    vertex_model: str | None = None
    thinking_budget: int | None = None

    # stockfish / random
    nodes: int | None = None
    seed: int = 2026

    # prompt and decoding (shared)
    think: Think = "tags"
    legal_list: bool = True
    max_tokens: int = 1024
    temperature: float = 0.0
    top_p: float = 1.0
    top_k: int = -1

    @property
    def require_think(self) -> bool:
        """Format reward and format rate require a think block for LLMs, not for engines."""
        return self.backend in ("vllm", "gemini")


def load(name_or_path: str | Path) -> Profile:
    p = Path(name_or_path)
    if p.suffix not in (".yaml", ".yml"):
        p = MODELS_DIR / f"{name_or_path}.yaml"
    return Profile.model_validate(yaml.safe_load(p.read_text()))
