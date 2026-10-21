"""Committed run configs and price table are well-formed."""

from __future__ import annotations

from pathlib import Path

import pytest

from ks.cloud.config import REPO, load_prices, load_run

RUNS = sorted((REPO / "configs" / "runs").glob("*.yaml"))


@pytest.mark.parametrize("path", RUNS, ids=lambda p: p.stem)
def test_run_config_parses_and_is_priced(path: Path):
    run = load_run(path)
    assert run.id == path.stem, "file name must match the run id"
    prices = load_prices()
    for region in run.regions():
        mp = prices.machine(region, run.machine)
        assert mp is not None, f"{run.machine} has no price in {region}"
        assert mp.gpus == run.gpus


def test_committed_prices_cover_the_planned_machines():
    prices = load_prices()
    for machine in ("g2-standard-8", "a2-ultragpu-1g", "a3-highgpu-1g"):
        p = prices.machine("us-central1", machine)
        assert p is not None and p.gpus == 1
