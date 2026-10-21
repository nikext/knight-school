"""The money gate: one test per rule in BUDGET.md §3.3 (and the M0 additions)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from ks.cloud import gate
from ks.cloud.config import Caps, CapsError, load_caps
from tests import factories as f
from tests.factories import NOW


def check(run=None, caps=None, prices=None, ledger=None, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("confirm", True)
    return gate.check(
        run or f.run(), caps or f.caps(), prices or f.prices(), ledger or f.ledger(), **kw
    )


def passed(result) -> gate.Ok:
    assert isinstance(result, gate.Ok), getattr(result, "reasons", None)
    return result


def refusal(result) -> gate.Refusal:
    assert isinstance(result, gate.Refusal), "expected a refusal"
    return result


def refused_because(result, fragment: str) -> bool:
    return any(fragment in r for r in refusal(result).reasons)


# --- the happy path and the arithmetic --------------------------------------


def test_ok_and_worst_case_arithmetic():
    res = passed(check())
    assert res.worst_case_usd == pytest.approx(10 * 3.00 * 1.05)
    # default run budget: one worst case per allowed attempt
    assert res.run_budget_usd == pytest.approx(3 * 31.5)


def test_worst_case_uses_the_most_expensive_candidate_region_and_the_disk():
    p = f.prices()
    p.disk["pd-balanced_usd_per_gb_month"] = 0.10
    res = check(run=f.run(zones=["us-central1-a", "europe-west4-a"], boot_disk_gb=200), prices=p)
    res = passed(res)
    per_hour = 3.10 + 200 * 0.10 / 730
    assert res.price_per_hour == pytest.approx(per_hour, abs=1e-6)
    assert res.worst_case_usd == pytest.approx(10 * per_hour * 1.05, abs=1e-3)


# --- pool ceiling and milestone allocation -----------------------------------


def test_refuses_over_pool_ceiling():
    # 340 already spent across milestones: +31.5 breaks the 360 ceiling
    led = f.ledger(f.charge("old", 340.0, milestone="M4"))
    res = check(ledger=led, caps=f.caps(remaining_usd=1000))
    assert refused_because(res, "ceiling $360.00 would be exceeded")


def test_running_jobs_worst_case_counts_against_the_pool():
    # an open M4 job with a big worst case: nothing spent, but 340 is "running"
    led = f.ledger(f.start("m4-sft-r1", milestone="M4", worst=340.0))
    res = check(ledger=led, caps=f.caps(remaining_usd=1000))
    assert refused_because(res, "ceiling $360.00 would be exceeded")


def test_refuses_over_milestone_allocation_without_contingency():
    led = f.ledger(f.charge("evals", 50.0, milestone="M3"))  # 50 + 31.5 > 70
    res = check(ledger=led)
    assert refused_because(res, "milestone M3 allocation $70.00 would be exceeded")
    assert refused_because(res, "--use-contingency")


def test_running_job_counts_against_its_milestone():
    led = f.ledger(
        f.start("m3-other-r1", worst=45.0),
        f.end("m3-other-r1", 0.0),  # closed, so not "one job at a time"
        f.charge("evals", 45.0),
    )
    res = check(ledger=led)
    assert refused_because(res, "milestone M3 allocation")


def test_milestone_overrun_allowed_with_contingency():
    led = f.ledger(f.charge("evals", 50.0, milestone="M3"))  # overrun 11.5 <= 50
    passed(check(ledger=led, use_contingency=True))


def test_contingency_cannot_be_exceeded():
    # M2 already overran by 40 (55 vs 15); M3 overrun 11.5 more -> 51.5 > 50
    led = f.ledger(
        f.charge("m2-big", 55.0, milestone="M2"), f.charge("evals", 50.0, milestone="M3")
    )
    res = check(ledger=led, use_contingency=True)
    assert refused_because(res, "contingency $50.00 would be exceeded")


def test_unknown_milestone_refused():
    res = check(run=f.run(id="m9-x-r1", milestone="M9"))
    assert refused_because(res, "has no allocation")


# --- prices ------------------------------------------------------------------


def test_refuses_unverified_prices():
    assert refused_because(check(prices=f.prices(verified=False)), "not verified")


def test_refuses_stale_prices():
    old = f.prices(fetched_on=NOW - timedelta(days=31))
    assert refused_because(check(prices=old), "31 days old")


def test_refuses_machine_without_a_price_in_some_candidate_region():
    res = check(run=f.run(zones=["us-central1-a", "asia-east1-a"]))
    assert refused_because(res, "no spot price for a2-ultragpu-1g in asia-east1")


# --- machine shape and hard job limits ---------------------------------------


def test_refuses_more_than_one_gpu():
    res = check(run=f.run(machine="a2-ultragpu-2g", gpus=2))
    assert refused_because(res, "2 GPUs requested")


def test_refuses_gpu_count_that_does_not_match_the_machine():
    res = check(run=f.run(machine="a2-ultragpu-2g", gpus=1))
    assert refused_because(res, "has 2 GPUs but the run says gpus: 1")


def test_cpu_only_spot_machine_is_allowed():
    res = check(
        run=f.run(
            id="m0-killswitch-test", milestone="M0", machine="e2-standard-2", gpus=0, max_hours=0.5
        )
    )
    passed(res)


def test_refuses_non_spot():
    assert refused_because(check(run=f.run(spot=False)), "not spot")


@pytest.mark.parametrize("hours", [24.5, 0, -1])
def test_refuses_max_hours_out_of_range(hours):
    assert refused_because(check(run=f.run(max_hours=hours)), "max_hours")


def test_24_hours_is_allowed_when_budget_permits():
    passed(check(run=f.run(id="m5-long-r1", milestone="M5", machine="g2-standard-8", max_hours=24)))


def test_refuses_vertex_backend_when_credit_does_not_cover_training():
    res = check(run=f.run(backend="vertex", pool="vertex"))
    assert refused_because(res, "Vertex custom training is not covered")


def test_refuses_gce_backend_on_vertex_pool():
    assert refused_because(check(run=f.run(pool="vertex")), "gce backend bills to the compute pool")


def test_refuses_run_id_that_does_not_match_its_milestone():
    assert refused_because(check(run=f.run(id="m4-e3-r1")), "does not start with milestone")


# --- user approval -------------------------------------------------------------


def test_refuses_without_confirm():
    res = check(confirm=False)
    assert refused_because(res, "--confirm missing")
    assert len(refusal(res).reasons) == 1  # everything else was fine


# --- caps.yaml consistency ------------------------------------------------------


def test_refuses_allocations_that_do_not_sum_to_the_ceiling():
    c = f.caps()
    c.allocations["compute"]["M3"] = 80  # now sums to 370
    assert refused_because(check(caps=c), "allocations sum to 370.00, ceiling is 360.00")


def test_load_caps_rejects_bad_sums(tmp_path):
    c = f.caps()
    c.allocations["vertex"]["M2"] = 60
    p = tmp_path / "caps.yaml"
    p.write_text(c.model_dump_json())  # JSON is valid YAML
    with pytest.raises(CapsError, match=r"pool vertex: allocations sum to 190\.00"):
        load_caps(p)


def test_refuses_caps_without_contingency_line():
    c = f.caps()
    del c.allocations["compute"]["contingency"]
    c.allocations["compute"]["M5"] += 50
    assert refused_because(check(caps=c), "no 'contingency' line")


def test_committed_caps_yaml_is_consistent():
    caps = load_caps()
    assert isinstance(caps, Caps)
    assert caps.limits.max_gpus_per_job == 1 and caps.limits.spot_only


# --- preemption retries and run identity ----------------------------------------


def test_retry_within_the_approved_run_budget_is_ok():
    led = f.ledger(
        f.start("m3-e2-dense-r1", worst=31.5, budget=70.0),
        f.end("m3-e2-dense-r1", 20.0, status="preempted"),
    )
    res = passed(check(ledger=led, attempt=2))
    assert res.run_budget_usd == 70.0  # the approved total, not a fresh default


def test_retry_that_would_break_the_run_budget_is_refused():
    led = f.ledger(
        f.start("m3-e2-dense-r1", worst=31.5, budget=50.0),
        f.end("m3-e2-dense-r1", 25.0, status="preempted"),
    )
    res = check(ledger=led, attempt=2)  # 25 + 31.5 > 50
    assert refused_because(res, "run budget $50.00 would be exceeded")


def test_retry_beyond_max_attempts_is_refused():
    led = f.ledger(
        f.start("m3-e2-dense-r1", worst=1, budget=500.0),
        f.end("m3-e2-dense-r1", 0.1, status="preempted"),
        f.start("m3-e2-dense-r1", attempt=2, worst=1),
        f.end("m3-e2-dense-r1", 0.1, attempt=2, status="preempted"),
        f.start("m3-e2-dense-r1", attempt=3, worst=1),
        f.end("m3-e2-dense-r1", 0.1, attempt=3, status="preempted"),
    )
    res = check(ledger=led, attempt=4, caps=f.caps(remaining_usd=1000))
    assert refused_because(res, "exceeds max_attempts 3")


def test_retry_while_previous_attempt_is_open_is_refused():
    led = f.ledger(f.start("m3-e2-dense-r1", worst=31.5, budget=100.0))
    res = check(ledger=led, attempt=2)
    assert refused_because(res, "still open in the ledger")


def test_retry_must_follow_the_last_attempt():
    led = f.ledger(f.start("m3-e2-dense-r1", worst=5, budget=100.0), f.end("m3-e2-dense-r1", 1.0))
    assert refused_because(check(ledger=led, attempt=3), "does not follow attempt 1")


def test_reusing_a_run_id_is_refused():
    led = f.ledger(f.start("m3-e2-dense-r1", worst=5), f.end("m3-e2-dense-r1", 1.0))
    assert refused_because(check(ledger=led), "already in the ledger")


def test_explicit_run_budget_below_one_worst_case_is_refused():
    assert refused_because(
        check(run=f.run(run_budget_usd=20.0)), "run budget $20.00 would be exceeded"
    )


def test_one_job_at_a_time():
    led = f.ledger(f.start("m3-throughput-r1", worst=5.0))
    assert refused_because(check(ledger=led), "m3-throughput-r1 attempt 1 is still open")


# --- credit expiry and the shared-credit headroom (ADR-013) ----------------------


def test_job_that_could_run_past_the_expiry_margin_is_refused():
    # deadline = 2026-11-12T00:00Z - 48 h = 2026-11-10T00:00Z
    late = datetime(2026, 11, 9, 16, 0, tzinfo=NOW.tzinfo)
    res = check(now=late, caps=f.caps(checked_on=late - timedelta(days=1)))  # ends 11-10 02:00Z
    assert refused_because(res, "is after 2026-11-10 00:00Z")


def test_job_that_ends_before_the_expiry_margin_is_ok():
    t = datetime(2026, 11, 9, 13, 0, tzinfo=NOW.tzinfo)  # ends 23:00Z
    passed(check(now=t, caps=f.caps(checked_on=t - timedelta(days=1))))


def test_pool_not_yet_usable_is_refused():
    c = f.caps()
    c.pools["compute"].usable_from = date(2026, 11, 13)
    assert refused_because(check(caps=c), "may only be used from 2026-11-13")


def test_stale_credit_reading_is_refused():
    res = check(caps=f.caps(checked_on=NOW - timedelta(days=8)))
    assert refused_because(res, "last read 8 days ago")


def test_credit_never_read_is_refused():
    res = check(caps=f.caps(remaining_usd=None, checked_on=None))
    assert refused_because(res, "never read")


def test_credit_drained_by_other_projects_is_refused():
    # ceiling and allocation are fine, but only $30 of credit is left: 0.9 x 30 = 27 < 31.5
    res = check(caps=f.caps(remaining_usd=30.0))
    assert refused_because(res, "exceeds the credit headroom $27.00")


def test_spend_since_the_credit_reading_reduces_the_headroom():
    checked = NOW - timedelta(days=2)
    led = f.ledger(
        f.charge("m2-build", 10.0, milestone="M2", ts=checked + timedelta(hours=1)),
        f.charge("m1-old", 5.0, milestone="M1", ts=checked - timedelta(hours=1)),
    )
    # 0.9 x 45 = 40.5; minus 10 spent after the reading (the 5 before is already in "remaining")
    res = check(ledger=led, caps=f.caps(remaining_usd=45.0, checked_on=checked))
    assert refused_because(res, "credit headroom $30.50")


def test_all_reasons_are_reported_together():
    res = check(run=f.run(spot=False, max_hours=30), prices=f.prices(verified=False), confirm=False)
    joined = " | ".join(refusal(res).reasons)
    for fragment in ("not spot", "max_hours", "not verified", "--confirm missing"):
        assert fragment in joined
