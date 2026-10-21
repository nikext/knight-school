"""Kill-switch decision logic and actions (infra/killswitch), without Google Cloud."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from killswitch_decision import Decision, Notification, act, decide, parse


def message(name: str, cost: float, amount: float) -> dict[str, Any]:
    body = {
        "budgetDisplayName": name,
        "costAmount": cost,
        "budgetAmount": amount,
        "costIntervalStart": "2026-10-01T00:00:00Z",
        "currencyCode": "USD",
    }
    return {
        "data": base64.b64encode(json.dumps(body).encode()).decode(),
        "attributes": {"schemaVersion": "1.0"},
    }


def test_parse_a_budget_message():
    assert parse(message("ks-net", 0.42, 5)) == Notification("ks-net", 0.42, 5.0)


@pytest.mark.parametrize(
    "name, cost, amount, stop",
    [
        ("ks-total-gross", 485.0, 540, False),  # 89.8%
        ("ks-total-gross", 486.0, 540, True),  # 90%
        ("ks-vertex-gross", 170.0, 180, True),
        ("ks-vertex-gross", 10.0, 180, False),
        ("ks-net", 0.99, 5, False),
        ("ks-net", 1.0, 5, True),
        ("someone-elses-budget", 1e6, 10, False),
    ],
)
def test_stop_thresholds(name, cost, amount, stop):
    assert decide(Notification(name, cost, amount), detach_enabled=True).stop is stop


def test_gross_budget_with_no_amount_fails_safe():
    assert decide(Notification("ks-total-gross", 0, 0), detach_enabled=False).stop


@pytest.mark.parametrize(
    "cost, enabled, detach", [(4.99, True, False), (5.0, True, True), (50.0, False, False)]
)
def test_billing_detach_needs_the_opt_in_and_five_dollars_net(cost, enabled, detach):
    d = decide(Notification("ks-net", cost, 5), detach_enabled=enabled)
    assert d.stop and d.detach is detach


def test_gross_budget_never_detaches_billing():
    assert not decide(Notification("ks-total-gross", 1000, 540), detach_enabled=True).detach


@dataclass
class Resp:
    status_code: int = 200
    body: dict = field(default_factory=dict)

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


@dataclass
class FakeSession:
    calls: list[tuple[str, str]] = field(default_factory=list)

    def request(self, method: str, url: str, **kw: Any) -> Resp:
        self.calls.append((method, url))
        if method == "GET" and url.endswith("/aggregated/instances"):
            assert kw["params"]["filter"] == "labels.app=knight-school"
            return Resp(
                body={
                    "items": {
                        "zones/us-central1-a": {"instances": [{"name": "ks-m3-x-a1"}]},
                        "zones/us-central1-b": {"warning": {"code": "NO_RESULTS_ON_PAGE"}},
                    }
                }
            )
        if method == "GET" and url.endswith("/customJobs"):
            if "us-central1" in url:
                return Resp(
                    body={"customJobs": [{"name": "projects/p/locations/us-central1/customJobs/7"}]}
                )
            return Resp(body={})
        if method == "DELETE":
            return Resp(status_code=404)  # already gone: still fine
        return Resp()


def test_stop_deletes_labelled_vms_and_cancels_jobs():
    s = FakeSession()
    out = act(Decision(True, False, "t"), s, "p", ["us-central1", "europe-west4"])
    assert (
        "DELETE",
        "https://compute.googleapis.com/compute/v1/projects/p/zones/us-central1-a/instances/ks-m3-x-a1",
    ) in s.calls
    assert (
        "POST",
        "https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/customJobs/7:cancel",
    ) in s.calls
    assert not any("billingInfo" in url for _, url in s.calls)
    assert out[0].endswith(": ok")


def test_detach_unlinks_billing():
    s = FakeSession()
    out = act(Decision(True, True, "t"), s, "p", ["us-central1"])
    assert ("PUT", "https://cloudbilling.googleapis.com/v1/projects/p/billingInfo") in s.calls
    assert out[-1] == "detach billing: ok"


def test_no_stop_means_no_calls():
    s = FakeSession()
    assert act(Decision(False, False, "t"), s, "p", ["us-central1"]) == [] and s.calls == []
