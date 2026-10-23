"""`ks launch`: gate -> ledger start -> create the spot VM (GCP.md §5).

The ``start`` event is written *before* anything is created, so a crash
between the two can only over-count, never hide, a cost.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ks.cloud import gate
from ks.cloud.config import LEDGER_PATH, REPO, Caps, Prices, RunConfig
from ks.cloud.gcp import CloudOps
from ks.cloud.ledger import (
    NOT_CREATED,
    STOCKOUT_NOTE,
    CreatedEvent,
    EndEvent,
    StartEvent,
    append_event,
    load_state,
)

STARTUP = REPO / "infra" / "vm_startup.sh"
SHUTDOWN = REPO / "infra" / "vm_shutdown.sh"


@dataclass
class LaunchResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    instance: str | None = None
    zone: str | None = None
    stockout: bool = False  # nothing was created because no zone had capacity


def job_seconds(max_hours: float) -> int:
    """Time the job itself may use: max-run-duration minus a reserve for the
    output sync and self-delete (10 min, or a third for very short jobs)."""
    total = int(max_hours * 3600)
    return total - min(600, total // 3)


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def create_args(
    run: RunConfig, attempt: int, zone: str, *, bucket: str, runner_sa: str
) -> list[str]:
    """The one gcloud command that creates a ks VM. Never typed by hand."""
    env = "".join(f"{k}={v}\n" for k, v in sorted(run.env.items()))
    metadata = {
        "ks-run-id": run.id,
        "ks-attempt": str(attempt),
        "ks-bucket": bucket,
        "ks-image": run.image,
        "ks-command": b64(run.command),
        "ks-env": b64(env),
        "ks-job-seconds": str(job_seconds(run.max_hours)),
        "ks-gpus": str(run.gpus),
    }
    if run.gpus:
        metadata["install-nvidia-driver"] = "True"
    labels = {
        "app": "knight-school",
        "run": run.id,
        "milestone": run.milestone.lower(),
        "attempt": str(attempt),
    }
    return [
        "compute",
        "instances",
        "create",
        run.instance_name(attempt),
        f"--zone={zone}",
        f"--machine-type={run.machine}",
        "--provisioning-model=SPOT",
        "--instance-termination-action=DELETE",
        f"--max-run-duration={int(run.max_hours * 3600)}s",
        "--maintenance-policy=TERMINATE",
        "--no-restart-on-failure",
        f"--image-family={run.vm_image_family}",
        f"--image-project={run.vm_image_project}",
        f"--boot-disk-size={run.boot_disk_gb}GB",
        "--boot-disk-type=pd-balanced",
        f"--service-account={runner_sa}",
        "--scopes=cloud-platform",
        "--labels=" + ",".join(f"{k}={v}" for k, v in labels.items()),
        f"--metadata-from-file=startup-script={STARTUP},shutdown-script={SHUTDOWN}",
        "--metadata=" + ",".join(f"{k}={v}" for k, v in metadata.items()),
    ]


def launch(
    run: RunConfig,
    *,
    caps: Caps,
    prices: Prices,
    ops: CloudOps,
    now: datetime,
    bucket: str,
    runner_sa: str,
    attempt: int = 1,
    confirm: bool = False,
    use_contingency: bool = False,
    approved: str = "",
    ledger_path: Path = LEDGER_PATH,
) -> LaunchResult:
    ledger = load_state(ledger_path)
    res = gate.check(
        run,
        caps,
        prices,
        ledger,
        now=now,
        attempt=attempt,
        confirm=confirm,
        use_contingency=use_contingency,
    )
    lines = list(res.lines)
    if not isinstance(res, gate.Ok):
        lines += [f"REFUSED: {r}" for r in res.reasons]
        return LaunchResult(ok=False, lines=lines)
    if run.backend != "gce":
        raise NotImplementedError(
            "Vertex custom jobs are not implemented: the vertex credit does not cover "
            "custom training (caps.yaml, ADR-013)"
        )

    name = run.instance_name(attempt)
    append_event(
        StartEvent(
            ts=now,
            id=run.id,
            attempt=attempt,
            milestone=run.milestone,
            pool=run.pool,
            kind="gce-spot",
            machine=run.machine,
            zones=run.zones,
            max_hours=run.max_hours,
            price_per_hour=res.price_per_hour,
            worst_case_usd=res.worst_case_usd,
            run_budget_usd=res.run_budget_usd,
            approved=approved or "unspecified",
            contingency=use_contingency,
            instance=name,
        ),
        ledger_path,
    )
    lines.append(f"ledger: start {run.id} attempt {attempt} (worst case ${res.worst_case_usd:.2f})")

    for zone in run.zones:
        cr = ops.create_instance(
            create_args(run, attempt, zone, bucket=bucket, runner_sa=runner_sa)
        )
        if cr.ok:
            append_event(
                CreatedEvent(ts=now, id=run.id, attempt=attempt, instance=name, zone=zone),
                ledger_path,
            )
            lines.append(f"created {name} in {zone}")
            return LaunchResult(ok=True, lines=lines, instance=name, zone=zone)
        if cr.stockout:
            lines.append(f"stockout in {zone}, trying the next zone")
            continue
        if cr.cancelled:
            if ops.instance_exists(name, zone):  # the create went through after all
                append_event(
                    CreatedEvent(ts=now, id=run.id, attempt=attempt, instance=name, zone=zone),
                    ledger_path,
                )
                lines.append(f"create of {name} in {zone} reported cancelled, but the VM exists")
                return LaunchResult(ok=True, lines=lines, instance=name, zone=zone)
            lines.append(f"create cancelled by GCE in {zone} (spot capacity), trying the next zone")
            continue
        lines.append(f"create failed in {zone}: {cr.message.strip()[-500:]}")
        fatal = True
        break
    else:
        fatal = False

    # Nothing was created: close the attempt at zero cost.
    append_event(
        EndEvent(
            ts=now,
            id=run.id,
            attempt=attempt,
            hours=0,
            actual_usd=0,
            status=NOT_CREATED,
            source="launcher",
            note="create failed" if fatal else STOCKOUT_NOTE,
        ),
        ledger_path,
    )
    lines.append("no VM was created; ledger attempt closed at $0")
    return LaunchResult(ok=False, lines=lines, stockout=not fatal)
