"""GRPO configs: arms change only the factor under test; the base parses and has sane shapes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ks.train import config as tc

ARMS = sorted(p for p in tc.TRAIN_DIR.glob("grpo_*.yaml"))


def test_base_config_shapes():
    cfg, _ = tc.load(tc.TRAIN_DIR / "grpo.yaml")
    assert cfg.completions_per_step == 512
    assert cfg.grad_accum * cfg.micro_batch == cfg.completions_per_step
    assert cfg.beta == 1e-3 and cfg.generations == 8 and cfg.steps == 200


@pytest.mark.parametrize("path", ARMS, ids=lambda p: p.stem)
def test_arms_only_change_the_factor_under_test(path: Path):
    merged, own = tc.resolve(path)
    assert set(own) <= tc.ARM_KEYS, f"{path.name} changes frozen keys {set(own) - tc.ARM_KEYS}"
    tc.GrpoConfig.model_validate(merged)


def test_arms_differ_from_each_other_only_in_task_reward():
    dense, _ = tc.load(tc.TRAIN_DIR / "grpo_dense.yaml")
    sparse, _ = tc.load(tc.TRAIN_DIR / "grpo_sparse.yaml")
    d, s = dense.model_dump(), sparse.model_dump()
    assert {k for k in d if d[k] != s[k]} == {"name", "task_reward"}


def test_set_overrides_parse_as_yaml():
    cfg, extra = tc.load(tc.TRAIN_DIR / "grpo_dense.yaml", ["steps=20", "eval_limit=null"])
    assert cfg.steps == 20 and cfg.eval_limit is None and extra == {"steps": 20, "eval_limit": None}
    with pytest.raises(ValueError):
        tc.parse_sets(["steps"])


def test_hash_ignores_the_name_but_not_hyperparameters():
    a, _ = tc.load(tc.TRAIN_DIR / "grpo_dense.yaml")
    b = a.model_copy(update={"name": "other"})
    c = a.model_copy(update={"learning_rate": 2e-5})
    assert a.hash() == b.hash() != c.hash()


def test_micro_batch_must_divide_the_step():
    with pytest.raises(ValidationError):
        tc.GrpoConfig(name="x", prompts_per_step=3, generations=3, micro_batch=4)


def test_sleep_mode_conflicts_with_the_dev_eval():
    with pytest.raises(ValidationError):
        tc.GrpoConfig(name="x", vllm_sleep=True, eval_every=25)
