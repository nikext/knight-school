from __future__ import annotations

from datetime import timedelta

import pytest

from ks.cloud.ledger import LedgerError, append_event, fold, load_state, read_events
from tests import factories as f
from tests.factories import NOW


def test_round_trip_through_the_file(tmp_path):
    path = tmp_path / "ledger.jsonl"
    events = [
        f.start("m3-a-r1", worst=10),
        f.created("m3-a-r1"),
        f.end("m3-a-r1", 4.2),
        f.charge("g", 0.5),
    ]
    for e in events:
        append_event(e, path)
    assert read_events(path) == events
    line = path.read_text().splitlines()[0]
    assert '"ts":"2026-10-22T07:00:00Z"' in line  # compact, UTC with Z


def test_budget_md_example_lines_parse(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        '{"ts":"2026-10-25T09:12:00Z","event":"start","id":"m3-e2-dense-r1","milestone":"M3","pool":"compute",'
        '"kind":"gce-spot","machine":"a2-ultragpu-1g","zone":"us-central1-a","max_hours":12,"price_per_hour":1.80,'
        '"worst_case_usd":22.68,"approved":"user, in session 2026-10-25"}\n'
        '{"ts":"2026-10-25T19:40:00Z","event":"end","id":"m3-e2-dense-r1","hours":10.47,"actual_usd":18.85,'
        '"status":"done","source":"gcs-marker"}\n'
        '{"ts":"2026-10-25T21:00:00Z","event":"charge","id":"m2-gemini-flash-test","milestone":"M2","pool":"vertex",'
        '"kind":"gemini-batch","actual_usd":11.20,"tokens_in":810000,"tokens_out":2900000}\n'
    )
    s = load_state(path)
    assert s.spent("compute") == pytest.approx(18.85)
    assert s.spent("vertex", "M2") == pytest.approx(11.20)
    assert s.open_attempts() == []


def test_bad_line_reports_its_number(tmp_path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"ts":"2026-10-25T21:00:00Z","event":"charge"}\n')
    with pytest.raises(LedgerError, match=":1:"):
        read_events(path)


def test_totals_per_pool_milestone_and_running():
    s = f.ledger(
        f.start("m3-a-r1", worst=10),
        f.end("m3-a-r1", 4.0),
        f.start("m4-b-r1", milestone="M4", worst=20),
        f.charge("gem", 1.5, milestone="M2", pool="vertex"),
    )
    assert s.spent("compute") == pytest.approx(4.0)
    assert s.running("compute") == pytest.approx(20.0)
    assert s.running("compute", "M3") == 0
    assert s.spent("vertex") == pytest.approx(1.5)
    assert [a.start.id for a in s.open_attempts()] == ["m4-b-r1"]


def test_spent_since_counts_only_later_ends_and_charges():
    s = f.ledger(
        f.start("m3-a-r1"),
        f.end("m3-a-r1", 4.0, ts=NOW - timedelta(days=3)),
        f.charge("c", 2.0, ts=NOW - timedelta(hours=2)),
    )
    assert s.spent("compute", since=NOW - timedelta(days=1)) == pytest.approx(2.0)


def test_overrun_is_spend_above_each_line():
    s = f.ledger(f.charge("a", 20.0, milestone="M2"), f.charge("b", 10.0, milestone="M3"))
    allocs = {"M2": 15, "M3": 70, "contingency": 50}
    assert s.overrun("compute", allocs) == pytest.approx(5.0)
    assert s.overrun("compute", allocs, extra={"M3": 65}) == pytest.approx(10.0)


def test_retry_attempts_and_run_cost():
    s = f.ledger(
        f.start("m3-a-r1", worst=10),
        f.end("m3-a-r1", 3.0, status="preempted"),
        f.start("m3-a-r1", attempt=2, worst=10),
    )
    assert [a.start.attempt for a in s.run_attempts("m3-a-r1")] == [1, 2]
    assert s.run_cost("m3-a-r1") == (3.0, 10.0)


@pytest.mark.parametrize(
    "events, msg",
    [
        ([f.end("m3-a-r1", 1.0)], "has no start"),
        ([f.start("m3-a-r1"), f.start("m3-a-r1")], "duplicate start"),
        ([f.start("m3-a-r1"), f.end("m3-a-r1", 1.0), f.end("m3-a-r1", 1.0)], "after its end"),
    ],
)
def test_inconsistent_ledgers_are_rejected(events, msg):
    with pytest.raises(LedgerError, match=msg):
        fold(events)


def test_committed_ledger_is_valid():
    load_state()  # raises on any malformed or inconsistent line
