"""An in-memory CloudOps for launch/watch/reconcile/sweep tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ks.cloud.gcp import CreateResult


@dataclass
class FakeCloud:
    project: str = "test-project"
    instances: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)  # (name, zone)
    disks: list[dict[str, Any]] = field(default_factory=list)
    objects: dict[str, str] = field(default_factory=dict)  # gs:// url -> text
    deletions: dict[str, datetime] = field(default_factory=dict)
    preemptions: set[str] = field(default_factory=set)
    jobs: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    endpoints: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    stockout_zones: set[str] = field(default_factory=set)
    cancelled_zones: set[str] = field(default_factory=set)
    cancelled_but_created: bool = False
    fail_message: str | None = None
    created: list[list[str]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)

    def create_instance(self, args: list[str]) -> CreateResult:
        self.created.append(args)
        name = args[3]
        zone = next(a.split("=", 1)[1] for a in args if a.startswith("--zone="))
        if zone in self.stockout_zones:
            return CreateResult(ok=False, stockout=True, message="ZONE_RESOURCE_POOL_EXHAUSTED")
        if zone in self.cancelled_zones and not self.cancelled_but_created:
            return CreateResult(
                ok=False, cancelled=True, message="Operation was canceled by user ''."
            )
        if self.fail_message:
            return CreateResult(ok=False, message=self.fail_message)
        labels = next(a.split("=", 1)[1] for a in args if a.startswith("--labels="))
        self.instances[(name, zone)] = {
            "name": name,
            "zone": f"zones/{zone}",
            "status": "RUNNING",
            "labels": dict(kv.split("=") for kv in labels.split(",")),
        }
        if zone in self.cancelled_zones:
            return CreateResult(
                ok=False, cancelled=True, message="Operation was canceled by user ''."
            )
        return CreateResult(ok=True)

    def instance_exists(self, name: str, zone: str) -> bool:
        return (name, zone) in self.instances

    def delete_instance(self, name: str, zone: str) -> None:
        self.instances.pop((name, zone), None)
        self.deleted.append(name)

    # test helpers
    def vm_finishes(self, name: str, zone: str, prefix: str, **markers: dict[str, Any]) -> None:
        """The VM writes its markers and disappears."""
        for marker, body in markers.items():
            self.objects[f"{prefix}/{marker}"] = json.dumps(body)
        self.instances.pop((name, zone), None)

    def read_text(self, url: str) -> str | None:
        return self.objects.get(url)

    def deletion_time(self, name: str) -> datetime | None:
        return self.deletions.get(name)

    def was_preempted(self, name: str) -> bool:
        return name in self.preemptions

    def list_instances(self) -> list[dict[str, Any]]:
        return list(self.instances.values())

    def list_disks(self) -> list[dict[str, Any]]:
        return self.disks

    def list_custom_jobs(self, region: str) -> list[dict[str, Any]]:
        return self.jobs.get(region, [])

    def cancel_custom_job(self, name: str, region: str) -> None:
        self.cancelled.append(name)

    def list_endpoints(self, region: str) -> list[dict[str, Any]]:
        return self.endpoints.get(region, [])

    def list_workbench(self, zone: str) -> list[dict[str, Any]]:
        return []
