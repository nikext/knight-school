"""Launch, reconcile, watch and sweep against an in-memory cloud."""

from __future__ import annotations

import base64
import json
from datetime import timedelta

import pytest

from ks.cloud import launch as L
from ks.cloud import reconcile as R
from ks.cloud.ledger import EndEvent, load_state
from ks.cloud.sweep import sweep
from ks.cloud.watch import watch
from tests import factories as f
from tests.factories import NOW
from tests.fake_cloud import FakeCloud

BUCKET = "gs://b"
SA = "ks-runner@p.iam.gserviceaccount.com"


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "ledger.jsonl"


def smoke(**kw):
    base = dict(
        id="m0-smoke-l4",
        milestone="M0",
        machine="g2-standard-8",
        max_hours=0.25,
        zones=["us-central1-a", "us-central1-b"],
        boot_disk_gb=50,
        command="nvidia-smi && sleep 120",
    )
    return f.run(**(base | kw))


def do_launch(cloud, ledger_path, run=None, *, now=NOW, confirm=True, attempt=1):
    return L.launch(
        run or smoke(),
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        now=now,
        bucket=BUCKET,
        runner_sa=SA,
        attempt=attempt,
        confirm=confirm,
        approved="test",
        ledger_path=ledger_path,
    )


def prefix(run_id="m0-smoke-l4", attempt=1):
    return R.marker_prefix(BUCKET, run_id, attempt)


# --- the gcloud command ---------------------------------------------------------


def test_create_args_have_every_hard_limit():
    args = L.create_args(smoke(), 1, "us-central1-a", bucket=BUCKET, runner_sa=SA)
    assert args[:4] == ["compute", "instances", "create", "ks-m0-smoke-l4-a1"]
    for flag in (
        "--provisioning-model=SPOT",
        "--instance-termination-action=DELETE",
        "--max-run-duration=900s",
        "--no-restart-on-failure",
        "--machine-type=g2-standard-8",
        f"--service-account={SA}",
        "--labels=app=knight-school,run=m0-smoke-l4,milestone=m0,attempt=1",
    ):
        assert flag in args
    meta = dict(
        kv.split("=", 1)
        for kv in next(a for a in args if a.startswith("--metadata=")).split("=", 1)[1].split(",")
    )
    assert base64.b64decode(meta["ks-command"]).decode() == "nvidia-smi && sleep 120"
    assert meta["ks-job-seconds"] == "600" and meta["ks-gpus"] == "1"
    assert not any(
        a.startswith("--accelerator") for a in args
    )  # the GPU comes with the machine type


def test_job_seconds_leaves_a_reserve():
    assert L.job_seconds(0.25) == 600  # 900 - 900 // 3
    assert L.job_seconds(10) == 36000 - 600


# --- launch -------------------------------------------------------------------------


def test_refused_launch_creates_nothing_and_writes_nothing(ledger_path):
    cloud = FakeCloud()
    res = do_launch(cloud, ledger_path, confirm=False)
    assert not res.ok and any("REFUSED: --confirm missing" in x for x in res.lines)
    assert cloud.created == [] and not ledger_path.exists()


def test_launch_writes_start_before_create_then_created(ledger_path):
    cloud = FakeCloud()
    res = do_launch(cloud, ledger_path)
    assert res.ok and res.zone == "us-central1-a"
    att = load_state(ledger_path).run_attempts("m0-smoke-l4")[0]
    assert att.is_open and att.created and att.created.zone == "us-central1-a"
    assert att.start.worst_case_usd == 0.1313  # 0.13125 rounded up


def test_stockout_tries_the_next_zone(ledger_path):
    cloud = FakeCloud(stockout_zones={"us-central1-a"})
    res = do_launch(cloud, ledger_path)
    assert res.ok and res.zone == "us-central1-b" and len(cloud.created) == 2


def test_cancelled_create_tries_the_next_zone(ledger_path):
    cloud = FakeCloud(cancelled_zones={"us-central1-a"})
    res = do_launch(cloud, ledger_path)
    assert res.ok and res.zone == "us-central1-b"
    assert any("cancelled by GCE" in line for line in res.lines)


def test_cancelled_create_that_left_a_vm_counts_as_created(ledger_path):
    cloud = FakeCloud(cancelled_zones={"us-central1-a"}, cancelled_but_created=True)
    res = do_launch(cloud, ledger_path)
    assert res.ok and res.zone == "us-central1-a" and len(cloud.instances) == 1
    att = load_state(ledger_path).run_attempts("m0-smoke-l4")[0]
    assert att.created is not None and att.created.zone == "us-central1-a"


def test_stockout_everywhere_closes_the_attempt_at_zero(ledger_path):
    cloud = FakeCloud(stockout_zones={"us-central1-a", "us-central1-b"})
    res = do_launch(cloud, ledger_path)
    assert not res.ok and res.stockout
    att = load_state(ledger_path).run_attempts("m0-smoke-l4")[0]
    assert att.end and att.end.status == "not-created" and att.end.actual_usd == 0
    assert att.stocked_out and not att.made_vm


def test_fatal_create_error_does_not_try_other_zones(ledger_path):
    cloud = FakeCloud(fail_message="Quota 'GPUS_ALL_REGIONS' exceeded. Limit: 0.0 globally.")
    res = do_launch(cloud, ledger_path)
    assert not res.ok and not res.stockout and len(cloud.created) == 1
    assert any("GPUS_ALL_REGIONS" in x for x in res.lines)
    att = load_state(ledger_path).run_attempts("m0-smoke-l4")[0]
    assert att.end and att.end.note == "create failed" and not att.stocked_out


# --- reconcile --------------------------------------------------------------------------


def launched(ledger_path):
    cloud = FakeCloud()
    assert do_launch(cloud, ledger_path).ok
    return cloud


def closed(ledger_path) -> EndEvent:
    end = load_state(ledger_path).run_attempts("m0-smoke-l4")[-1].end
    assert end is not None, "attempt is still open"
    return end


def test_reconcile_leaves_running_vms_open(ledger_path):
    cloud = launched(ledger_path)
    assert R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=5), ledger_path) == [
        "m0-smoke-l4 attempt 1: still running (ks-m0-smoke-l4-a1)"
    ]


def test_reconcile_uses_the_ended_marker(ledger_path):
    cloud = launched(ledger_path)
    t = NOW + timedelta(minutes=6)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1", "us-central1-a", prefix(), ended={"ts": t.isoformat(), "exit_code": 0}
    )
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    end = closed(ledger_path)
    assert end.status == "done" and end.source == "gcs-marker"
    assert end.hours == pytest.approx(8 / 60, abs=1e-3)  # 6 min + 2 min deletion pad
    assert end.actual_usd == pytest.approx(end.hours * 0.50, abs=1e-4)


def test_reconcile_failed_job(ledger_path):
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        ended={"ts": (NOW + timedelta(minutes=1)).isoformat(), "exit_code": 3},
    )
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    assert closed(ledger_path).status == "failed" and closed(ledger_path).note == "exit code 3"


def test_reconcile_preempted_marker(ledger_path):
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
    )
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    assert closed(ledger_path).status == "preempted"


def test_failed_exit_on_a_preemption_counts_as_preempted(ledger_path):
    # the job exits 143 on SIGTERM and `ended` lands before the shutdown script's marker
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        ended={"ts": (NOW + timedelta(minutes=3)).isoformat(), "exit_code": 143},
    )
    cloud.preemptions.add("ks-m0-smoke-l4-a1")
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    assert closed(ledger_path).status == "preempted"


def test_ended_marker_flagged_preempted_counts_as_preempted(ledger_path):
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        ended={"ts": (NOW + timedelta(minutes=3)).isoformat(), "exit_code": 143, "preempted": True},
    )
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    assert closed(ledger_path).status == "preempted"


def test_clean_exit_stays_done_even_if_preempted_later(ledger_path):
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        ended={"ts": (NOW + timedelta(minutes=3)).isoformat(), "exit_code": 0},
    )
    cloud.preemptions.add("ks-m0-smoke-l4-a1")
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=20), ledger_path)
    assert closed(ledger_path).status == "done"


def test_reconcile_shutdown_at_the_time_limit_is_a_timeout(ledger_path):
    cloud = launched(ledger_path)
    cloud.vm_finishes(
        "ks-m0-smoke-l4-a1",
        "us-central1-a",
        prefix(),
        shutdown={"ts": (NOW + timedelta(minutes=15)).isoformat()},
    )
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=30), ledger_path)
    end = closed(ledger_path)
    assert end.status == "timeout" and end.hours <= 0.25 + 2 / 60 + 1e-9


def test_reconcile_falls_back_to_the_audit_log(ledger_path):
    cloud = launched(ledger_path)
    cloud.instances.clear()
    cloud.deletions["ks-m0-smoke-l4-a1"] = NOW + timedelta(minutes=4)
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=30), ledger_path)
    end = closed(ledger_path)
    assert end.source == "audit-log" and end.status == "vanished"
    assert end.hours == pytest.approx(6 / 60, abs=1e-3)


def test_audit_log_preemption_without_marker_counts_as_preempted(ledger_path):
    cloud = launched(ledger_path)
    cloud.instances.clear()
    cloud.deletions["ks-m0-smoke-l4-a1"] = NOW + timedelta(minutes=4)
    cloud.preemptions.add("ks-m0-smoke-l4-a1")
    R.reconcile(cloud, BUCKET, NOW + timedelta(minutes=30), ledger_path)
    end = closed(ledger_path)
    assert end.source == "audit-log" and end.status == "preempted"


def test_reconcile_without_evidence_charges_max_hours(ledger_path):
    cloud = launched(ledger_path)
    cloud.instances.clear()
    R.reconcile(cloud, BUCKET, NOW + timedelta(hours=1), ledger_path)
    end = closed(ledger_path)
    assert end.source == "max-hours-fallback"
    assert end.hours == pytest.approx(0.25 + 2 / 60, abs=1e-3)


# --- watch ------------------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


def test_watch_relaunches_after_preemption_then_finishes(ledger_path):
    cloud, clock = launched(ledger_path), Clock()
    script = iter(
        [
            lambda: cloud.vm_finishes(
                "ks-m0-smoke-l4-a1",
                "us-central1-a",
                prefix(),
                preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
            ),
            lambda: cloud.vm_finishes(
                "ks-m0-smoke-l4-a2",
                "us-central1-a",
                prefix(attempt=2),
                ended={"ts": (NOW + timedelta(minutes=12)).isoformat(), "exit_code": 0},
            ),
        ]
    )

    def sleep(_):
        clock.t += timedelta(minutes=5)
        next(script)()

    status = watch(
        smoke(),
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        bucket=BUCKET,
        runner_sa=SA,
        approved="test",
        ledger_path=ledger_path,
        clock=clock,
        sleep=sleep,
        log=lambda _: None,
    )
    assert status == "done"
    atts = load_state(ledger_path).run_attempts("m0-smoke-l4")
    assert [a.end.status for a in atts if a.end] == ["preempted", "done"]
    assert "preemption retry" in atts[1].start.approved


def test_watch_stops_when_a_retry_would_break_the_run_budget(ledger_path):
    cloud, clock = FakeCloud(), Clock()
    run = smoke(run_budget_usd=0.2)  # one worst case is 0.13125
    assert do_launch(cloud, ledger_path, run=run).ok

    def sleep(_):
        clock.t += timedelta(minutes=5)
        cloud.vm_finishes(
            "ks-m0-smoke-l4-a1",
            "us-central1-a",
            prefix(),
            preempted={"ts": (NOW + timedelta(minutes=14)).isoformat()},
        )

    status = watch(
        run,
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        bucket=BUCKET,
        runner_sa=SA,
        approved="test",
        ledger_path=ledger_path,
        clock=clock,
        sleep=sleep,
        log=lambda _: None,
    )
    assert status == "retry-refused"
    assert len(load_state(ledger_path).run_attempts("m0-smoke-l4")) == 1


def test_watch_does_not_retry_a_vm_that_was_stopped(ledger_path):
    cloud, clock = launched(ledger_path), Clock()

    def sleep(_):
        clock.t += timedelta(minutes=5)
        cloud.vm_finishes(
            "ks-m0-smoke-l4-a1",
            "us-central1-a",
            prefix(),
            shutdown={"ts": (NOW + timedelta(minutes=2)).isoformat()},
        )

    status = watch(
        smoke(),
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        bucket=BUCKET,
        runner_sa=SA,
        approved="test",
        ledger_path=ledger_path,
        clock=clock,
        sleep=sleep,
        log=lambda _: None,
    )
    assert status == "stopped" and len(cloud.created) == 1


ZONES = {"us-central1-a", "us-central1-b"}


def watch_with(cloud, clock, run, sleep, ledger_path, logs=None):
    return watch(
        run,
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        bucket=BUCKET,
        runner_sa=SA,
        approved="test",
        ledger_path=ledger_path,
        clock=clock,
        sleep=sleep,
        log=(logs.append if logs is not None else lambda _: None),
    )


def test_watch_waits_out_a_stockout_then_runs(ledger_path):
    cloud, clock = launched(ledger_path), Clock()
    run = smoke(stockout_wait_hours=2)
    slept: list[float] = []
    ticks = iter(
        [
            lambda: (  # preempted; the retry finds no capacity anywhere
                cloud.vm_finishes(
                    "ks-m0-smoke-l4-a1",
                    "us-central1-a",
                    prefix(),
                    preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
                ),
                cloud.stockout_zones.update(ZONES),
            ),
            lambda: None,  # attempt 3 finds none either
            lambda: cloud.stockout_zones.clear(),  # capacity is back for attempt 4
            lambda: cloud.vm_finishes(
                "ks-m0-smoke-l4-a4",
                "us-central1-a",
                prefix(attempt=4),
                ended={"ts": clock.t.isoformat(), "exit_code": 0},
            ),
        ]
    )

    def sleep(s):
        slept.append(s)
        clock.t += timedelta(seconds=s)
        next(ticks)()

    assert watch_with(cloud, clock, run, sleep, ledger_path) == "done"
    atts = load_state(ledger_path).run_attempts("m0-smoke-l4")
    assert [a.end.status for a in atts if a.end] == [
        "preempted",
        "not-created",
        "not-created",
        "done",
    ]
    assert "stockout retry" in atts[2].start.approved and "stockout retry" in atts[3].start.approved
    assert slept[1] == 900  # STOCKOUT_RETRY


def test_watch_gives_up_after_stockout_wait_hours(ledger_path):
    cloud, clock = launched(ledger_path), Clock()
    run = smoke(stockout_wait_hours=1)
    first = True

    def sleep(s):
        nonlocal first
        clock.t += timedelta(seconds=s)
        if first:
            first = False
            cloud.vm_finishes(
                "ks-m0-smoke-l4-a1",
                "us-central1-a",
                prefix(),
                preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
            )
            cloud.stockout_zones.update(ZONES)

    assert watch_with(cloud, clock, run, sleep, ledger_path) == "stockout"
    atts = load_state(ledger_path).run_attempts("m0-smoke-l4")
    tries = [a for a in atts if a.stocked_out]
    assert len(tries) == 5  # at 0, 15, 30, 45 and 60 min after the first stockout
    assert tries[-1].end and tries[0].end
    assert tries[-1].end.ts - tries[0].end.ts == timedelta(hours=1)
    assert sum(a.actual_usd for a in tries) == 0


def test_watch_without_stockout_wait_ends_on_a_stockout(ledger_path):
    cloud, clock = launched(ledger_path), Clock()

    def sleep(_):
        clock.t += timedelta(minutes=5)
        cloud.vm_finishes(
            "ks-m0-smoke-l4-a1",
            "us-central1-a",
            prefix(),
            preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
        )
        cloud.stockout_zones.update(ZONES)

    assert watch_with(cloud, clock, smoke(), sleep, ledger_path) == "retry-failed"
    assert len(load_state(ledger_path).run_attempts("m0-smoke-l4")) == 2


def test_watch_does_not_retry_a_create_error(ledger_path):
    cloud, clock = launched(ledger_path), Clock()

    def sleep(_):
        clock.t += timedelta(minutes=5)
        cloud.vm_finishes(
            "ks-m0-smoke-l4-a1",
            "us-central1-a",
            prefix(),
            preempted={"ts": (NOW + timedelta(minutes=3)).isoformat()},
        )
        cloud.fail_message = "Invalid value for field 'resource.machineType'"

    run = smoke(stockout_wait_hours=12)
    assert watch_with(cloud, clock, run, sleep, ledger_path) == "retry-failed"
    atts = load_state(ledger_path).run_attempts("m0-smoke-l4")
    assert len(atts) == 2 and atts[1].end and atts[1].end.note == "create failed"


def test_watch_picks_up_a_first_attempt_stockout(ledger_path):
    cloud, clock = FakeCloud(stockout_zones=set(ZONES)), Clock()
    run = smoke(stockout_wait_hours=1)
    assert not do_launch(cloud, ledger_path, run=run).ok

    def sleep(s):
        clock.t += timedelta(seconds=s)
        if cloud.stockout_zones:
            cloud.stockout_zones.clear()
        else:
            name, zone = next(iter(cloud.instances))
            cloud.vm_finishes(
                name, zone, prefix(attempt=2), ended={"ts": clock.t.isoformat(), "exit_code": 0}
            )

    assert watch_with(cloud, clock, run, sleep, ledger_path) == "done"
    atts = load_state(ledger_path).run_attempts("m0-smoke-l4")
    assert [a.end.status for a in atts if a.end] == ["not-created", "done"]


def test_watch_deletes_a_vm_that_outlives_its_ended_marker(ledger_path):
    cloud, clock = launched(ledger_path), Clock()
    cloud.objects[f"{prefix()}/ended"] = json.dumps(
        {"ts": (NOW + timedelta(minutes=1)).isoformat(), "exit_code": 0}
    )

    def sleep(_):
        clock.t += timedelta(minutes=6)

    status = watch(
        smoke(),
        caps=f.caps(),
        prices=f.prices(),
        ops=cloud,
        bucket=BUCKET,
        runner_sa=SA,
        approved="test",
        ledger_path=ledger_path,
        clock=clock,
        sleep=sleep,
        log=lambda _: None,
    )
    assert status == "done" and cloud.deleted == ["ks-m0-smoke-l4-a1"]


# --- sweep -----------------------------------------------------------------------------------------


def test_sweep_clean():
    lines, found = sweep(FakeCloud())
    assert found == [] and "CLEAN" in lines[0]


def test_sweep_flags_unexpected_and_deletes_only_ours(ledger_path):
    cloud = launched(ledger_path)
    cloud.instances[("someone-elses", "us-central1-c")] = {
        "name": "someone-elses",
        "zone": "zones/us-central1-c",
        "status": "RUNNING",
        "labels": {},
    }
    cloud.jobs["us-central1"] = [
        {
            "name": "projects/p/locations/us-central1/customJobs/1",
            "displayName": "ks-job",
            "state": "JOB_STATE_RUNNING",
            "labels": {"app": "knight-school"},
        }
    ]
    lines, found = sweep(cloud, delete=True)
    assert len(found) == 3
    assert any("UNEXPECTED" in x and "someone-elses" in x for x in lines)
    assert cloud.deleted == ["ks-m0-smoke-l4-a1"]
    assert cloud.cancelled == ["ks-job"]
    assert ("someone-elses", "us-central1-c") in cloud.instances
