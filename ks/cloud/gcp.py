"""The only place ks.cloud talks to Google Cloud: a thin wrapper over gcloud.

Launch, watch, reconcile and sweep take a ``CloudOps`` so tests can use a fake.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

GCLOUD = os.environ.get("GCLOUD", str(Path("~/google-cloud-sdk/bin/gcloud").expanduser()))

# Messages GCE returns when a zone has no spot capacity; anything else is fatal.
STOCKOUT_MARKERS = (
    "ZONE_RESOURCE_POOL_EXHAUSTED",
    "does not have enough resources available",
    "resource pool exhausted",
    "STOCKOUT",
)
# A spot create can also be cancelled by GCE while provisioning when the capacity goes
# (m3-smoke-l4-r2, us-central1-a). The launcher treats it as a stockout once it has checked
# that no VM was left behind.
CANCELLED_MARKERS = ("Operation was canceled",)


@dataclass(frozen=True)
class CreateResult:
    ok: bool
    stockout: bool = False
    cancelled: bool = False  # GCE cancelled the create; check no VM exists before moving on
    message: str = ""


class CloudOps(Protocol):
    project: str

    def create_instance(self, args: list[str]) -> CreateResult: ...
    def instance_exists(self, name: str, zone: str) -> bool: ...
    def delete_instance(self, name: str, zone: str) -> None: ...
    def read_text(self, url: str) -> str | None: ...
    def deletion_time(self, name: str) -> datetime | None: ...
    def was_preempted(self, name: str) -> bool: ...
    def list_instances(self) -> list[dict[str, Any]]: ...
    def list_disks(self) -> list[dict[str, Any]]: ...
    def list_custom_jobs(self, region: str) -> list[dict[str, Any]]: ...
    def cancel_custom_job(self, name: str, region: str) -> None: ...
    def list_endpoints(self, region: str) -> list[dict[str, Any]]: ...
    def list_workbench(self, zone: str) -> list[dict[str, Any]]: ...


class GcloudOps:
    def __init__(self, project: str, gcloud: str = GCLOUD):
        self.project = project
        self.gcloud = gcloud

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        env = os.environ | {"CLOUDSDK_CORE_DISABLE_PROMPTS": "1"}
        return subprocess.run(
            [self.gcloud, *args, f"--project={self.project}"],
            capture_output=True,
            text=True,
            check=check,
            env=env,
        )

    def _json(self, *args: str) -> list[dict[str, Any]]:
        out = self._run(*args, "--format=json").stdout
        return json.loads(out or "[]")

    def create_instance(self, args: list[str]) -> CreateResult:
        p = self._run(*args, check=False)
        msg = (p.stderr or "") + (p.stdout or "")
        if p.returncode == 0:
            return CreateResult(ok=True, message=msg)
        return CreateResult(
            ok=False,
            stockout=any(m in msg for m in STOCKOUT_MARKERS),
            cancelled=any(m in msg for m in CANCELLED_MARKERS),
            message=msg,
        )

    def instance_exists(self, name: str, zone: str) -> bool:
        p = self._run(
            "compute",
            "instances",
            "describe",
            name,
            f"--zone={zone}",
            "--format=value(name)",
            check=False,
        )
        if p.returncode == 0:
            return True
        if "was not found" in p.stderr or "notFound" in p.stderr:
            return False
        raise RuntimeError(f"cannot tell whether {name} exists: {p.stderr.strip()}")

    def delete_instance(self, name: str, zone: str) -> None:
        self._run("compute", "instances", "delete", name, f"--zone={zone}", "--quiet")

    def read_text(self, url: str) -> str | None:
        p = self._run("storage", "cat", url, check=False)
        return p.stdout if p.returncode == 0 else None

    def deletion_time(self, name: str) -> datetime | None:
        """When GCE deleted or preempted the instance, from the audit log."""
        flt = (
            f'resource.type="gce_instance" AND protoPayload.resourceName:"instances/{name}" AND '
            '(protoPayload.methodName:"instances.delete" OR protoPayload.methodName:"instances.preempted" '
            'OR protoPayload.methodName:"instances.stop")'
        )
        p = self._run(
            "logging", "read", flt, "--freshness=30d", "--limit=5", "--format=json", check=False
        )
        if p.returncode != 0:
            return None
        entries = json.loads(p.stdout or "[]")
        stamps = [datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) for e in entries]
        return max(stamps) if stamps else None

    def was_preempted(self, name: str) -> bool:
        """True if the audit log has GCE's `instances.preempted` event for the instance."""
        flt = (
            f'resource.type="gce_instance" AND protoPayload.resourceName:"instances/{name}" AND '
            'protoPayload.methodName:"instances.preempted"'
        )
        p = self._run(
            "logging", "read", flt, "--freshness=30d", "--limit=1", "--format=json", check=False
        )
        return p.returncode == 0 and bool(json.loads(p.stdout or "[]"))

    def list_instances(self) -> list[dict[str, Any]]:
        return self._json("compute", "instances", "list")

    def list_disks(self) -> list[dict[str, Any]]:
        return self._json("compute", "disks", "list")

    def list_custom_jobs(self, region: str) -> list[dict[str, Any]]:
        return self._json(
            "ai",
            "custom-jobs",
            "list",
            f"--region={region}",
            "--filter=state:(JOB_STATE_RUNNING JOB_STATE_PENDING JOB_STATE_QUEUED)",
        )

    def cancel_custom_job(self, name: str, region: str) -> None:
        self._run("ai", "custom-jobs", "cancel", name, f"--region={region}")

    def list_endpoints(self, region: str) -> list[dict[str, Any]]:
        return self._json("ai", "endpoints", "list", f"--region={region}")

    def list_workbench(self, zone: str) -> list[dict[str, Any]]:
        p = self._run(
            "workbench", "instances", "list", f"--location={zone}", "--format=json", check=False
        )
        return json.loads(p.stdout or "[]") if p.returncode == 0 else []
