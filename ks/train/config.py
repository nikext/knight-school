"""Training run configs (`configs/train/*.yaml`, TRAINING.md §4, §5).

GRPO: `configs/train/grpo.yaml` holds the hyperparameters, frozen in M3
(ADR-019, revised by ADR-021 and ADR-022) for every arm. An arm file names it as
`base:` and may only change the factor its experiment tests (`ARM_KEYS`);
`tests/test_train_config.py` enforces that on every committed arm. Smoke runs
change more with `--set key=value`, and run.json records every override.

SFT (the primer, ADR-023): `configs/train/sft.yaml` and files based on it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ks.chess.rewards import TaskReward
from ks.cloud.config import REPO

TRAIN_DIR = REPO / "configs" / "train"

# What an arm may change on top of the frozen base: the factor under test (RESEARCH.md §4).
ARM_KEYS = frozenset({"name", "task_reward", "model", "init_ckpt", "legal_list", "lora_r"})


class GrpoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    model: str = "qwen3.5-2b"  # profile in configs/models/
    init_ckpt: str | None = None  # merged SFT checkpoint (M4), gs:// or local; default: the profile
    task_reward: TaskReward = "dense"
    legal_list: bool = True  # E5b drops it (changes the prompt hash)

    data: str = "data/positions/rl_train.parquet"
    positions: int | None = None  # use only the first N rl_train rows (smoke tests)

    lora_r: int = 32
    lora_alpha: int = 64
    lora_dropout: float = 0.0

    learning_rate: float = 1e-5
    warmup_steps: int = 10
    lr_scheduler: str = "constant_with_warmup"
    weight_decay: float = 0.0
    max_grad_norm: float = 1.0

    prompts_per_step: int = 64
    generations: int = 8
    micro_batch: int = 8  # completions per forward/backward; accumulation covers the rest
    max_completion: int = 1024
    temperature: float = 1.0
    beta: float = 1e-3
    loss_type: str = "dapo"  # TRL 1.16's default, recorded in ADR-018
    mask_truncated: bool = False
    # v3 (ADR-022): rollouts stop at the first </answer>, which is kept. Under v2 nothing
    # stopped generation there, and post-answer rambling ran on to the cap (ADR-021).
    stop_at_answer: bool = False
    # Entropy bonus (TRL's entropy_coef). Adaptive (Skywork-OR1, ADR-021): the coefficient
    # rises by entropy_coef_delta each step the mean token entropy is <= entropy_target,
    # falls otherwise, and applies only at or below the target.
    entropy_coef: float = 0.0
    entropy_adaptive: bool = False
    entropy_target: float = 0.2
    entropy_coef_delta: float = 0.005
    # v4 (ADR-027): with N > 0 there is no bonus for the first N steps; then the target becomes
    # min(entropy_target, their mean entropy). A start above the target runs as with a fixed one.
    entropy_start_steps: int = 0
    steps: int = 200

    eval_set: str = "dev500"
    eval_every: int = 25
    eval_limit: int | None = None  # puzzles; None = the whole set
    eval_at_start: bool = True

    save_every: int = 25
    keep_last: int = 2

    vllm_mem: float = 0.45
    vllm_sleep: bool = False
    gradient_checkpointing: bool = True
    seed: int = 2026
    samples_per_step: int = 16  # completions written to samples.jsonl each step

    @property
    def completions_per_step(self) -> int:
        return self.prompts_per_step * self.generations

    @property
    def grad_accum(self) -> int:
        return self.completions_per_step // self.micro_batch

    @model_validator(mode="after")
    def _shapes(self) -> GrpoConfig:
        if self.completions_per_step % self.micro_batch:
            raise ValueError(
                f"micro_batch {self.micro_batch} must divide prompts_per_step x generations "
                f"= {self.completions_per_step}"
            )
        if self.vllm_sleep and self.eval_every:
            raise ValueError("the dev eval generates on the colocated engine; it can't sleep")
        return self

    def hash(self) -> str:
        """Hash of everything that shapes training (the name does not)."""
        body = self.model_dump(exclude={"name"})
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12]


class SftConfig(BaseModel):
    """Primer SFT (TRAINING.md §5, ADR-023): full fine-tune, loss on the answer tokens only."""

    model_config = ConfigDict(extra="forbid")

    name: str
    model: str = "qwen3.5-2b"  # profile in configs/models/
    data: str = "data/primer/M"  # a dir of shard-*.jsonl.zst, local or gs://
    examples: int | None = None  # use only the first N (smoke tests)
    max_length: int = 2048  # longer examples are dropped and counted (the primer's are ~143 tokens)

    learning_rate: float = 1e-5
    lr_scheduler: str = "cosine"
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    max_grad_norm: float = 1.0
    epochs: int = 1
    # One optimizer step = `step_examples` examples drawn at random, sorted by length inside the
    # step and cut into micro-batches of `micro_batch` (padded, not packed: ADR-023).
    step_examples: int = 1728  # ~0.25M tokens at 143 tokens per example
    micro_batch: int = 64
    gradient_checkpointing: bool = False
    # Regex over parameter names: only matches train. None = every language-model parameter
    # (the vision tower never trains). For laptop smoke tests that can't fit a full fine-tune.
    train_params: str | None = None

    save_minutes: float = Field(default=30.0, gt=0)  # wall-clock checkpoints (TRAINING.md §7)
    save_steps: int | None = None  # also every N steps (smoke tests; deterministic)
    keep_last: int = 1
    probe_prompts: int = 32  # dev500 RL prompts, greedy, at every checkpoint: format and legal rate
    probe_max_tokens: int = 32
    seed: int = 2026

    @property
    def grad_accum(self) -> int:
        return self.step_examples // self.micro_batch

    @model_validator(mode="after")
    def _shapes(self) -> SftConfig:
        if self.step_examples % self.micro_batch:
            raise ValueError(
                f"micro_batch {self.micro_batch} must divide step_examples {self.step_examples}"
            )
        return self

    def hash(self) -> str:
        body = self.model_dump(exclude={"name"})
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12]


def _read(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def resolve(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """(merged fields, the arm's own overrides). `base:` is relative to the arm file."""
    p = Path(path)
    if not p.exists() and not p.is_absolute():
        p = TRAIN_DIR / p
    raw = _read(p)
    base = raw.pop("base", None)
    if base is None:
        return raw, {}
    merged, _ = resolve(p.parent / base)
    return merged | raw, raw


def parse_sets(sets: list[str]) -> dict[str, Any]:
    """`key=value` strings, values parsed as YAML (so `steps=20`, `eval_limit=null`)."""
    out = {}
    for s in sets:
        k, sep, v = s.partition("=")
        if not sep:
            raise ValueError(f"--set wants key=value, got {s!r}")
        out[k.strip()] = yaml.safe_load(v)
    return out


def load(path: str | Path, sets: list[str] | None = None) -> tuple[GrpoConfig, dict[str, Any]]:
    """The effective config and the `--set` overrides applied on top of the file."""
    fields, _ = resolve(path)
    extra = parse_sets(sets or [])
    return GrpoConfig.model_validate(fields | extra), extra


def load_sft(path: str | Path, sets: list[str] | None = None) -> tuple[SftConfig, dict[str, Any]]:
    fields, _ = resolve(path)
    extra = parse_sets(sets or [])
    return SftConfig.model_validate(fields | extra), extra
