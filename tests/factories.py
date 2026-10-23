"""Small builders for caps, prices, runs and ledgers used across the tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from ks.cloud.config import Caps, Limits, MachinePrice, Pool, Prices, RunConfig
from ks.cloud.ledger import ChargeEvent, CreatedEvent, EndEvent, LedgerState, StartEvent, fold

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def caps(**pool_overrides: Any) -> Caps:
    compute = {
        "credit": "test annual",
        "scope": "all of Google Cloud",
        "remaining_usd": 440.0,
        "checked_on": NOW - timedelta(days=1),
        "expires": date(2026, 11, 12),
        "ceiling": 360.0,
    } | pool_overrides
    return Caps(
        currency="USD",
        pools={
            "compute": Pool(**compute),
            "vertex": Pool(
                credit="test marketing",
                scope="Gemini",
                remaining_usd=209.0,
                checked_on=NOW - timedelta(days=1),
                expires=date(2027, 4, 8),
                usable_from=date(2026, 11, 13),
                ceiling=180.0,
            ),
        },
        allocations={
            "compute": {
                "M0": 5,
                "M1": 1,
                "M2": 15,
                "M3": 70,
                "M4": 100,
                "M5": 110,
                "M6": 9,
                "contingency": 50,
            },
            "vertex": {
                "M0": 1,
                "M1": 0,
                "M2": 50,
                "M3": 0,
                "M4": 0,
                "M5": 110,
                "M6": 4,
                "contingency": 15,
            },
        },
        limits=Limits(),
    )


def prices(verified: bool = True, fetched_on: datetime | None = None) -> Prices:
    def table(l4: float, a100: float) -> dict[str, MachinePrice]:
        return {
            "g2-standard-8": MachinePrice(gpu="nvidia-l4", gpus=1, usd_per_hour=l4),
            "a2-ultragpu-1g": MachinePrice(gpu="nvidia-a100-80gb", gpus=1, usd_per_hour=a100),
            "a2-ultragpu-2g": MachinePrice(gpu="nvidia-a100-80gb", gpus=2, usd_per_hour=2 * a100),
            "e2-standard-2": MachinePrice(gpu="none", gpus=0, usd_per_hour=0.02),
        }

    return Prices(
        verified=verified,
        fetched_on=fetched_on or NOW - timedelta(days=1),
        source="test",
        gce_spot={"us-central1": table(0.50, 3.00), "europe-west4": table(0.52, 3.10)},
        disk={"pd-balanced_usd_per_gb_month": 0.0},  # keep the arithmetic readable
    )


def run(**overrides: Any) -> RunConfig:
    base: dict[str, Any] = {
        "id": "m3-e2-dense-r1",
        "milestone": "M3",
        "machine": "a2-ultragpu-1g",
        "zones": ["us-central1-a"],
        "max_hours": 10,
        "image": "img",
        "command": "true",
    }
    return RunConfig(**(base | overrides))


def start(
    id: str,
    *,
    attempt: int = 1,
    milestone: str = "M3",
    pool: str = "compute",
    worst: float = 10.0,
    budget: float | None = None,
    ts: datetime | None = None,
) -> StartEvent:
    return StartEvent(
        ts=ts or NOW - timedelta(hours=5),
        id=id,
        attempt=attempt,
        milestone=milestone,
        pool=pool,
        kind="gce-spot",
        machine="a2-ultragpu-1g",
        zone="us-central1-a",
        max_hours=10,
        price_per_hour=worst / 10.5,
        worst_case_usd=worst,
        run_budget_usd=budget,
        approved="test",
    )


def created(id: str, *, attempt: int = 1, ts: datetime | None = None) -> CreatedEvent:
    return CreatedEvent(
        ts=ts or NOW - timedelta(hours=5),
        id=id,
        attempt=attempt,
        instance=f"ks-{id}-a{attempt}",
        zone="us-central1-a",
    )


def end(
    id: str,
    usd: float,
    *,
    attempt: int = 1,
    ts: datetime | None = None,
    status: str = "done",
    note: str | None = None,
) -> EndEvent:
    return EndEvent(
        ts=ts or NOW - timedelta(hours=1),
        id=id,
        attempt=attempt,
        hours=1.0,
        actual_usd=usd,
        status=status,
        source="test",
        note=note,
    )


def charge(
    id: str, usd: float, *, milestone: str = "M3", pool: str = "compute", ts: datetime | None = None
) -> ChargeEvent:
    return ChargeEvent(
        ts=ts or NOW - timedelta(hours=1),
        id=id,
        milestone=milestone,
        pool=pool,
        kind="test",
        actual_usd=usd,
    )


def ledger(*events: Any) -> LedgerState:
    return fold(events)
