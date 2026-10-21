"""What the kill switch does with one budget notification (BUDGET.md §3.5).

Pure decision logic plus the actions, which go through an injectable HTTP
session so they can be tested without Google Cloud. Budgets publish several
times a day, not only on threshold crossings, so the ratio is computed here
from ``costAmount / budgetAmount``. Every action is idempotent.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol

GROSS_BUDGETS = ("ks-total-gross", "ks-vertex-gross")
NET_BUDGET = "ks-net"
GROSS_STOP_FRACTION = 0.9
NET_STOP_USD = 1.0
NET_DETACH_USD = 5.0
LABEL = "knight-school"


@dataclass(frozen=True)
class Notification:
    budget: str
    cost: float
    amount: float
    currency: str = "USD"


@dataclass(frozen=True)
class Decision:
    stop: bool
    detach: bool
    reason: str


def parse(message: dict[str, Any]) -> Notification:
    """A Pub/Sub message (as in a CloudEvent's data["message"]) -> Notification."""
    data = json.loads(base64.b64decode(message["data"]))
    return Notification(
        budget=data["budgetDisplayName"],
        cost=float(data["costAmount"]),
        amount=float(data["budgetAmount"]),
        currency=data.get("currencyCode", "USD"),
    )


def decide(n: Notification, *, detach_enabled: bool) -> Decision:
    if n.budget in GROSS_BUDGETS:
        if n.amount <= 0:
            return Decision(
                True, False, f"{n.budget}: budget amount {n.amount} is not positive; fail safe"
            )
        ratio = n.cost / n.amount
        if ratio >= GROSS_STOP_FRACTION:
            return Decision(
                True, False, f"{n.budget} at {ratio:.0%} (>= {GROSS_STOP_FRACTION:.0%})"
            )
        return Decision(False, False, f"{n.budget} at {ratio:.0%}, below {GROSS_STOP_FRACTION:.0%}")
    if n.budget == NET_BUDGET:
        detach = detach_enabled and n.cost >= NET_DETACH_USD
        if n.cost >= NET_STOP_USD:
            why = f"net spend ${n.cost:.2f} >= ${NET_STOP_USD:.2f}: credits no longer cover usage"
            if detach:
                why += f"; >= ${NET_DETACH_USD:.2f}, detaching billing"
            return Decision(True, detach, why)
        return Decision(False, False, f"net spend ${n.cost:.2f}, below ${NET_STOP_USD:.2f}")
    return Decision(False, False, f"budget {n.budget!r} is not one of ours; ignored")


# --- actions ------------------------------------------------------------------


class Session(Protocol):
    def request(self, method: str, url: str, **kw: Any) -> Any: ...


COMPUTE = "https://compute.googleapis.com/compute/v1"
BILLING = "https://cloudbilling.googleapis.com/v1"


def _ok(resp: Any) -> bool:
    # 404: already gone. Anything else non-2xx is reported but doesn't stop the sweep.
    return resp.status_code < 300 or resp.status_code == 404


def delete_instances(session: Session, project: str) -> list[str]:
    url = f"{COMPUTE}/projects/{project}/aggregated/instances"
    resp = session.request("GET", url, params={"filter": f"labels.app={LABEL}"})
    resp.raise_for_status()
    done = []
    for scope, item in (resp.json().get("items") or {}).items():
        zone = scope.removeprefix("zones/")
        for inst in item.get("instances", []):
            r = session.request(
                "DELETE", f"{COMPUTE}/projects/{project}/zones/{zone}/instances/{inst['name']}"
            )
            done.append(f"delete {zone}/{inst['name']}: {'ok' if _ok(r) else r.status_code}")
    return done


def cancel_custom_jobs(session: Session, project: str, regions: list[str]) -> list[str]:
    done = []
    flt = (
        f'labels.app="{LABEL}" AND (state="JOB_STATE_RUNNING" OR state="JOB_STATE_PENDING" '
        'OR state="JOB_STATE_QUEUED")'
    )
    for region in regions:
        base = (
            f"https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}"
        )
        resp = session.request("GET", f"{base}/customJobs", params={"filter": flt})
        resp.raise_for_status()
        for job in resp.json().get("customJobs", []):
            r = session.request(
                "POST", f"https://{region}-aiplatform.googleapis.com/v1/{job['name']}:cancel"
            )
            done.append(f"cancel {job['name']}: {'ok' if _ok(r) else r.status_code}")
    return done


def detach_billing(session: Session, project: str) -> str:
    r = session.request(
        "PUT", f"{BILLING}/projects/{project}/billingInfo", json={"billingAccountName": ""}
    )
    return f"detach billing: {'ok' if _ok(r) else r.status_code}"


def act(decision: Decision, session: Session, project: str, regions: list[str]) -> list[str]:
    if not decision.stop:
        return []
    out = delete_instances(session, project) + cancel_custom_jobs(session, project, regions)
    if decision.detach:
        out.append(detach_billing(session, project))
    return out
