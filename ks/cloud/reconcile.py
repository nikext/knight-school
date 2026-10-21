"""`ks reconcile`: close finished attempts in the ledger with their real cost.

The end time comes from, in order of preference:
1. the run's GCS markers (``ended``, ``preempted``, ``shutdown``),
2. the VM's deletion time in the audit log,
3. ``max_hours`` after the start, the conservative fallback.

Billing starts at the ``created`` event (or the ``start`` event if there is
none). Two minutes are added for the deletion itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ks.cloud.config import LEDGER_PATH
from ks.cloud.gcp import CloudOps
from ks.cloud.ledger import Attempt, EndEvent, append_event, load_state

DELETE_PAD = timedelta(minutes=2)


def marker_prefix(bucket: str, run_id: str, attempt: int) -> str:
    return f"{bucket}/runs/{run_id}/attempts/{attempt}"


def read_marker(ops: CloudOps, bucket: str, att: Attempt, name: str) -> dict[str, Any] | None:
    text = ops.read_text(f"{marker_prefix(bucket, att.start.id, att.start.attempt)}/{name}")
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def marker_time(m: dict[str, Any]) -> datetime | None:
    return datetime.fromisoformat(m["ts"].replace("Z", "+00:00")) if m.get("ts") else None


def instance_zones(att: Attempt) -> list[str]:
    if att.created:
        return [att.created.zone]
    return att.start.zones or ([att.start.zone] if att.start.zone else [])


def instance_name(att: Attempt) -> str:
    return att.start.instance or f"ks-{att.start.id}-a{att.start.attempt}"


def is_running(att: Attempt, ops: CloudOps) -> bool:
    return any(ops.instance_exists(instance_name(att), z) for z in instance_zones(att))


def close(att: Attempt, ops: CloudOps, bucket: str, now: datetime) -> EndEvent | None:
    """The end event for a finished attempt, or None while its VM still exists."""
    if is_running(att, ops):
        return None
    s = att.start
    begin = att.created.ts if att.created else s.ts
    limit = begin + timedelta(hours=s.max_hours)

    end_at: datetime | None = None
    note = None
    if (m := read_marker(ops, bucket, att, "ended")) is not None:
        end_at, source = marker_time(m), "gcs-marker"
        rc = m.get("exit_code")
        status = "done" if rc == 0 else "failed"
        note = f"exit code {rc}"
    elif (m := read_marker(ops, bucket, att, "preempted")) is not None:
        end_at, source, status = marker_time(m), "gcs-marker", "preempted"
    elif (m := read_marker(ops, bucket, att, "shutdown")) is not None:
        end_at, source = marker_time(m), "gcs-marker"
        near_limit = end_at is not None and end_at >= limit - timedelta(minutes=3)
        status = "timeout" if near_limit else "stopped"
    elif (t := ops.deletion_time(instance_name(att))) is not None:
        # The shutdown script has ~30 s to write its marker and can miss (m2-screen-a100-r2 did),
        # so a preemption in the audit log counts as one: the watcher may then retry.
        status = "preempted" if ops.was_preempted(instance_name(att)) else "vanished"
        end_at, source = t, "audit-log"
    else:
        source, status = "max-hours-fallback", "unknown"

    if end_at is None:
        end_at = limit
        source = "max-hours-fallback"
    end_at = min(end_at + DELETE_PAD, limit + DELETE_PAD)
    hours = max(0.0, (end_at - begin).total_seconds() / 3600)
    return EndEvent(
        ts=now,
        id=s.id,
        attempt=s.attempt,
        hours=round(hours, 4),
        actual_usd=round(hours * s.price_per_hour, 4),
        status=status,
        source=source,
        zone=att.created.zone if att.created else None,
        note=note,
    )


def reconcile(
    ops: CloudOps, bucket: str, now: datetime, ledger_path: Path = LEDGER_PATH
) -> list[str]:
    lines = []
    for att in load_state(ledger_path).open_attempts():
        end = close(att, ops, bucket, now)
        label = f"{att.start.id} attempt {att.start.attempt}"
        if end is None:
            lines.append(f"{label}: still running ({instance_name(att)})")
            continue
        append_event(end, ledger_path)
        lines.append(
            f"{label}: closed {end.status}, {end.hours:.3f} h, ${end.actual_usd:.4f} (source: {end.source})"
        )
    return lines or ["nothing open in the ledger"]
