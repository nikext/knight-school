"""The append-only money ledger (BUDGET.md §4) and its fold into totals.

Events, one JSON object per line in costs/ledger.jsonl:

- ``start``: written *before* a billable resource is created. Its
  ``worst_case_usd`` counts against every cap until a matching ``end``.
- ``created``: the resource exists (instance name, zone). Reconcile uses its
  timestamp as the billing start.
- ``end``: the attempt is over, with the actual hours and cost.
- ``charge``: a cost with no lifetime (Gemini calls, storage, ...).

A preemption retry is a new ``start`` with the same ``id`` and the next
``attempt`` number. So is a stockout retry (ADR-020): an attempt that found no
capacity in any zone ends at once as ``not-created`` at $0 with
``note: stockout``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from ks.cloud.config import LEDGER_PATH

# The status of an attempt the launcher closed at $0 because no VM was created, and the
# note that says it was for lack of capacity (retryable) rather than a create error.
NOT_CREATED = "not-created"
STOCKOUT_NOTE = "stockout"


class LedgerError(ValueError):
    """The ledger is inconsistent; fix it by hand before launching anything."""


def now_ts() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: datetime


class StartEvent(_Event):
    event: Literal["start"] = "start"
    id: str
    attempt: int = 1
    milestone: str
    pool: str
    kind: str
    machine: str | None = None
    zone: str | None = None
    zones: list[str] = []
    max_hours: float
    price_per_hour: float
    worst_case_usd: float
    run_budget_usd: float | None = None
    approved: str
    contingency: bool = False
    instance: str | None = None


class CreatedEvent(_Event):
    event: Literal["created"] = "created"
    id: str
    attempt: int = 1
    instance: str
    zone: str


class EndEvent(_Event):
    event: Literal["end"] = "end"
    id: str
    attempt: int = 1
    hours: float = Field(ge=0)
    actual_usd: float = Field(ge=0)
    status: str
    source: str
    zone: str | None = None
    note: str | None = None


class ChargeEvent(_Event):
    model_config = ConfigDict(extra="allow")  # tokens_in, tokens_out, ...
    event: Literal["charge"] = "charge"
    id: str
    milestone: str
    pool: str
    kind: str
    actual_usd: float = Field(ge=0)


Event = Annotated[StartEvent | CreatedEvent | EndEvent | ChargeEvent, Field(discriminator="event")]
_EVENT = TypeAdapter(Event)


def parse_event(line: str) -> Event:
    return _EVENT.validate_json(line)


def read_events(path: Path = LEDGER_PATH) -> list[Event]:
    if not path.exists():
        return []
    events: list[Event] = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(parse_event(line))
        except Exception as e:
            raise LedgerError(f"{path}:{n}: {e}") from e
    return events


def append_event(event: Event, path: Path = LEDGER_PATH) -> None:
    """Append one event and fsync, so a crash right after can't lose it."""
    line = json.dumps(event.model_dump(mode="json", exclude_none=True), separators=(",", ":"))
    with path.open("a") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


# --- folding ----------------------------------------------------------------


@dataclass
class Attempt:
    start: StartEvent
    created: CreatedEvent | None = None
    end: EndEvent | None = None

    @property
    def key(self) -> tuple[str, int]:
        return (self.start.id, self.start.attempt)

    @property
    def is_open(self) -> bool:
        return self.end is None

    @property
    def actual_usd(self) -> float:
        return self.end.actual_usd if self.end else 0.0

    @property
    def running_worst_usd(self) -> float:
        return self.start.worst_case_usd if self.end is None else 0.0

    @property
    def made_vm(self) -> bool:
        """False only for an attempt the launcher closed at $0 because nothing was created."""
        return not (self.end and self.end.status == NOT_CREATED)

    @property
    def stocked_out(self) -> bool:
        return bool(self.end and self.end.status == NOT_CREATED and self.end.note == STOCKOUT_NOTE)


@dataclass
class LedgerState:
    attempts: dict[tuple[str, int], Attempt] = field(default_factory=dict)
    charges: list[ChargeEvent] = field(default_factory=list)

    # Every query takes the pool explicitly: the pools are separate credits.

    def _attempts(self, pool: str, milestone: str | None = None) -> Iterable[Attempt]:
        for a in self.attempts.values():
            if a.start.pool == pool and (milestone is None or a.start.milestone == milestone):
                yield a

    def spent(
        self, pool: str, milestone: str | None = None, since: datetime | None = None
    ) -> float:
        """Actual cost of closed attempts and charges (optionally after ``since``)."""
        total = 0.0
        for a in self._attempts(pool, milestone):
            if a.end and (since is None or a.end.ts > since):
                total += a.end.actual_usd
        for c in self.charges:
            in_scope = c.pool == pool and (milestone is None or c.milestone == milestone)
            if in_scope and (since is None or c.ts > since):
                total += c.actual_usd
        return total

    def running(self, pool: str, milestone: str | None = None) -> float:
        """Worst case of attempts that have started and not ended."""
        return sum(a.running_worst_usd for a in self._attempts(pool, milestone))

    def open_attempts(self, pool: str | None = None) -> list[Attempt]:
        return [
            a
            for a in self.attempts.values()
            if a.is_open and (pool is None or a.start.pool == pool)
        ]

    def run_attempts(self, run_id: str) -> list[Attempt]:
        return sorted(
            (a for a in self.attempts.values() if a.start.id == run_id),
            key=lambda a: a.start.attempt,
        )

    def run_cost(self, run_id: str) -> tuple[float, float]:
        """(actual spent, running worst case) over all attempts of one run."""
        atts = self.run_attempts(run_id)
        return sum(a.actual_usd for a in atts), sum(a.running_worst_usd for a in atts)

    def milestones(self, pool: str) -> set[str]:
        ms = {a.start.milestone for a in self._attempts(pool)}
        return ms | {c.milestone for c in self.charges if c.pool == pool}

    def overrun(
        self, pool: str, allocations: Mapping[str, float], extra: Mapping[str, float] | None = None
    ) -> float:
        """Total spend above each milestone's line (booked against contingency).

        ``extra`` adds hypothetical spend per milestone, so the gate can ask
        "what would the overrun be if this job hit its worst case?".
        """
        extra = extra or {}
        total = 0.0
        for m in self.milestones(pool) | set(extra):
            if m == "contingency":
                continue
            used = self.spent(pool, m) + self.running(pool, m) + extra.get(m, 0.0)
            total += max(0.0, used - allocations.get(m, 0.0))
        return total


def fold(events: Iterable[Event]) -> LedgerState:
    state = LedgerState()
    for e in events:
        if isinstance(e, ChargeEvent):
            state.charges.append(e)
            continue
        key = (e.id, e.attempt)
        if isinstance(e, StartEvent):
            if key in state.attempts:
                raise LedgerError(f"duplicate start for {e.id} attempt {e.attempt}")
            state.attempts[key] = Attempt(start=e)
            continue
        att = state.attempts.get(key)
        if att is None:
            raise LedgerError(f"{e.event} for {e.id} attempt {e.attempt} has no start")
        if att.end is not None:
            raise LedgerError(f"{e.event} for {e.id} attempt {e.attempt} after its end")
        if isinstance(e, CreatedEvent):
            att.created = e
        else:
            att.end = e
    return state


def load_state(path: Path = LEDGER_PATH) -> LedgerState:
    return fold(read_events(path))
