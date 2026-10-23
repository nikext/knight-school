"""Checkpoint copies: completeness marker, latest, prune, pull (local store = the GCS logic)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ks.train import ckpt as kc


def make(local: Path, step: int) -> Path:
    d = local / f"checkpoint-{step}"
    (d / "sub").mkdir(parents=True)
    (d / "adapter_model.safetensors").write_text(f"w{step}")
    (d / "sub" / "rng.pth").write_text("r")
    return d


def test_push_marks_complete_and_latest_finds_it(tmp_path: Path):
    store, root = kc.LocalStore(), str(tmp_path / "remote")
    assert kc.latest(store, root) is None
    assert kc.push(store, make(tmp_path / "w", 25), root, keep=2) == 2
    assert kc.latest(store, root) == 25


def test_an_unfinished_copy_is_ignored(tmp_path: Path):
    store, root = kc.LocalStore(), str(tmp_path / "remote")
    kc.push(store, make(tmp_path / "w", 25), root, keep=2)
    # a preemption cut the copy of 50 short: files but no marker
    store.put(
        make(tmp_path / "w", 50) / "adapter_model.safetensors",
        root,
        "checkpoint-50/adapter_model.safetensors",
    )
    assert kc.latest(store, root) == 25


def test_prune_keeps_the_newest_complete(tmp_path: Path):
    store, root = kc.LocalStore(), str(tmp_path / "remote")
    for s in (25, 50, 75):
        kc.push(store, make(tmp_path / "w", s), root, keep=2)
    assert sorted(kc.steps(store, root)) == [50, 75]
    assert kc.latest(store, root) == 75
    assert not (Path(root) / "checkpoint-25").exists()


def test_prune_spares_a_newer_partial_copy(tmp_path: Path):
    store, root = kc.LocalStore(), str(tmp_path / "remote")
    kc.push(store, make(tmp_path / "w", 25), root, keep=1)
    store.put(
        make(tmp_path / "w", 50) / "adapter_model.safetensors",
        root,
        "checkpoint-50/adapter_model.safetensors",
    )
    assert kc.prune(store, root, keep=1) == []
    assert sorted(kc.steps(store, root)) == [25, 50]


def test_pull_restores_the_tree(tmp_path: Path):
    store, root = kc.LocalStore(), str(tmp_path / "remote")
    kc.push(store, make(tmp_path / "w", 25), root, keep=2)
    out = kc.pull(store, root, 25, tmp_path / "resume")
    assert (out / "adapter_model.safetensors").read_text() == "w25"
    assert (out / "sub" / "rng.pth").exists() and (out / kc.COMPLETE).exists()


def test_push_wants_a_checkpoint_dir(tmp_path: Path):
    with pytest.raises(ValueError):
        kc.push(kc.LocalStore(), tmp_path, str(tmp_path / "r"), keep=2)
