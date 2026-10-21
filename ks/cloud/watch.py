"""`ks watch`: follow one run until it ends; relaunch after preemption.

Every ``interval`` seconds: is the VM still there? If it is gone, close the
attempt (reconcile). Only a ``preempted`` attempt is retried, and only
through the gate, which enforces ``max_attempts`` and the approved run
budget. A VM that outlives its ``ended`` marker or its ``max_hours`` is
deleted here as a second line of defence.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from ks.cloud import reconcile
from ks.cloud.config import LEDGER_PATH, Caps, Prices, RunConfig, utcnow
from ks.cloud.gcp import CloudOps
from ks.cloud.launch import launch
from ks.cloud.ledger import append_event, load_state

ENDED_GRACE = timedelta(minutes=10)
OVERTIME_GRACE = timedelta(minutes=15)


def watch(
    run: RunConfig,
    *,
    caps: Caps,
    prices: Prices,
    ops: CloudOps,
    bucket: str,
    runner_sa: str,
    approved: str,
    interval: float = 300,
    ledger_path: Path = LEDGER_PATH,
    clock: Callable[[], datetime] = lambda: utcnow().replace(microsecond=0),
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> str:
    while True:
        attempts = load_state(ledger_path).run_attempts(run.id)
        if not attempts:
            log(f"{run.id}: not in the ledger")
            return "missing"
        cur = attempts[-1]
        label = f"{run.id} attempt {cur.start.attempt}"

        if cur.is_open:
            now = clock()
            end = reconcile.close(cur, ops, bucket, now)
            if end is None:
                _enforce_limits(cur, ops, bucket, now, log)
                log(f"{now:%H:%M:%SZ} {label}: running")
                sleep(interval)
                continue
            append_event(end, ledger_path)
            log(f"{label}: {end.status}, {end.hours:.3f} h, ${end.actual_usd:.4f} ({end.source})")
            status = end.status
        else:
            assert cur.end is not None
            status = cur.end.status

        if status != "preempted":
            return status
        if cur.start.attempt >= run.max_attempts:
            log(f"{run.id}: preempted {cur.start.attempt} times, max_attempts reached; stopping")
            return "preempted"

        res = launch(
            run,
            caps=caps,
            prices=prices,
            ops=ops,
            now=clock(),
            bucket=bucket,
            runner_sa=runner_sa,
            attempt=cur.start.attempt + 1,
            confirm=True,
            use_contingency=cur.start.contingency,
            approved=f"{approved} (preemption retry, covered by the run's approval)",
            ledger_path=ledger_path,
        )
        for line in res.lines:
            log(line)
        if not res.ok:
            return (
                "retry-refused"
                if any(x.startswith("REFUSED") for x in res.lines)
                else "retry-failed"
            )


def _enforce_limits(cur, ops: CloudOps, bucket: str, now: datetime, log) -> None:
    name = reconcile.instance_name(cur)
    zone = cur.created.zone if cur.created else None
    if zone is None:
        return
    begin = cur.created.ts if cur.created else cur.start.ts
    if now > begin + timedelta(hours=cur.start.max_hours) + OVERTIME_GRACE:
        log(f"{name}: past max_hours + {OVERTIME_GRACE}; deleting it")
        ops.delete_instance(name, zone)
        return
    ended = reconcile.read_marker(ops, bucket, cur, "ended")
    if ended is not None:
        t = reconcile.marker_time(ended)
        if t is not None and now > t + ENDED_GRACE:
            log(f"{name}: job ended at {t:%H:%MZ} but the VM did not delete itself; deleting it")
            ops.delete_instance(name, zone)
