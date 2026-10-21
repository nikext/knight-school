"""`ks sweep`: list everything that can bill by the hour (GCP.md §8).

The project is dedicated, so *every* instance, disk, Vertex job, endpoint and
Workbench instance is listed, not just labelled ones. Anything without the
``app=knight-school`` label is flagged UNEXPECTED: something we didn't
create, which means stop and tell the user. ``delete=True`` removes only our
own resources (labelled, or ``ks-`` boot disks left behind).
"""

from __future__ import annotations

from dataclasses import dataclass

from ks.cloud.gcp import CloudOps

REGIONS = ["us-central1", "europe-west4"]
WORKBENCH_ZONES = [f"us-central1-{z}" for z in "abcf"] + [f"europe-west4-{z}" for z in "abc"]


@dataclass
class Found:
    kind: str
    name: str
    where: str
    state: str
    ours: bool

    def line(self) -> str:
        tag = "" if self.ours else "  <-- UNEXPECTED (not created by ks)"
        return f"{self.kind:<13} {self.name:<40} {self.where:<16} {self.state}{tag}"


def _last(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def _ours(item: dict) -> bool:
    return (item.get("labels") or {}).get("app") == "knight-school"


def find(ops: CloudOps) -> list[Found]:
    found = [
        Found("instance", i["name"], _last(i["zone"]), i.get("status", "?"), _ours(i))
        for i in ops.list_instances()
    ]
    for d in ops.list_disks():
        users = [_last(u) for u in d.get("users", [])]
        state = f"attached to {', '.join(users)}" if users else "UNATTACHED"
        found.append(
            Found(
                "disk", d["name"], _last(d["zone"]), state, _ours(d) or d["name"].startswith("ks-")
            )
        )
    for region in REGIONS:
        for j in ops.list_custom_jobs(region):
            found.append(
                Found(
                    "vertex-job",
                    j.get("displayName", j["name"]),
                    region,
                    j.get("state", "?"),
                    _ours(j),
                )
            )
        for e in ops.list_endpoints(region):
            found.append(
                Found("endpoint", e.get("displayName", e["name"]), region, "deployed", False)
            )
    for zone in WORKBENCH_ZONES:
        for w in ops.list_workbench(zone):
            found.append(Found("workbench", _last(w["name"]), zone, w.get("state", "?"), False))
    return found


def sweep(ops: CloudOps, delete: bool = False) -> tuple[list[str], list[Found]]:
    found = find(ops)
    if not found:
        return [
            f"sweep {ops.project}: CLEAN (no instances, disks, Vertex jobs, endpoints or notebooks)"
        ], []
    lines = [f"sweep {ops.project}: {len(found)} resource(s)"] + [f.line() for f in found]
    if any(not f.ours for f in found):
        lines.append(
            "UNEXPECTED resources found: stop and tell the user before doing anything else."
        )
    if delete:
        for f in found:
            if f.kind == "instance" and f.ours:
                ops.delete_instance(f.name, f.where)
                lines.append(f"deleted instance {f.name}")
            elif f.kind == "vertex-job" and f.ours:
                ops.cancel_custom_job(f.name, f.where)
                lines.append(f"cancelled vertex job {f.name}")
            elif not f.ours:
                lines.append(f"left {f.kind} {f.name}: not ours, the user decides")
        lines.append("boot disks auto-delete with their instance; re-run `make sweep` to confirm")
    return lines, found
