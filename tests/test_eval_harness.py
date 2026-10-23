from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import chess
import pytest

from ks.eval import harness, probe, report, sets
from ks.eval.backends import Completion, RandomBackend, Request
from ks.eval.profile import Profile, load

LLM = Profile(name="fake-llm", backend="vllm", hf_repo="fake/model")


class Fake:
    """A backend that answers with fn(request), costing `usd_per_call` each."""

    def __init__(self, fn: Callable[[Request], str], usd_per_call: float = 0.0) -> None:
        self.fn, self.usd, self.cost_usd, self.calls = fn, usd_per_call, 0.0, 0

    def generate(self, reqs: list[Request], n: int = 1) -> list[list[Completion]]:
        out = []
        for r in reqs:
            self.calls += 1
            self.cost_usd += self.usd
            out.append([Completion(self.fn(r), 100, 20) for _ in range(n)])
        return out

    def close(self) -> None:
        pass


@pytest.fixture(scope="module")
def puzzles() -> list[sets.Puzzle]:
    return sets.spread(sets.load_puzzles("dev500"), 36)


def _solutions(puzzles: list[sets.Puzzle]) -> dict[str, str]:
    return {f"{p.id}-{pos['ply']}": pos["solution_san"] for p in puzzles for pos in p.positions}


def run(puzzles, fn, profile=LLM, **kw):
    backend = fn if isinstance(fn, Fake) else Fake(fn)
    return harness.run(harness.EvalRun(profile, "dev500", puzzles, **kw), backend)


def test_sets_load_and_spread(puzzles):
    full = sets.load_puzzles("dev500")
    assert len(full) == 500 and all(1 <= len(p.positions) <= 4 for p in full)
    assert len(puzzles) == 36 and len({p.bin for p in puzzles}) == 12
    assert len(sets.load_puzzles("test500")) == 500
    with pytest.raises(ValueError):
        sets.load_puzzles("train")


def test_oracle_scores_perfect(puzzles):
    sol = _solutions(puzzles)
    res = run(puzzles, lambda r: f"<think>easy</think><answer>{sol[r.id]}</answer>")
    s = res["summary"]
    assert s["puzzles"] == 36 and s["positions"] == len(sol)
    for k in ("solve", "move_acc", "legal", "format"):
        assert s[k]["value"] == 1.0
    assert s["rating"]["bound"] == "above"
    assert res["header"]["prompt_hash"] == "c728de49e119"


def test_all_illegal(puzzles):
    s = run(puzzles, lambda r: "<think>x</think><answer>Zz9</answer>")["summary"]
    assert s["legal"]["value"] == 0.0 and s["solve"]["value"] == 0.0
    assert s["format"]["value"] == 1.0
    assert s["rating"]["bound"] == "below"


def test_first_move_only_right_solves_only_one_movers(puzzles):
    sol = _solutions(puzzles)

    def first_only(r: Request) -> str:
        ply = r.id.rsplit("-", 1)[1]
        return f"<think>x</think><answer>{sol[r.id] if ply == '1' else 'Zz9'}</answer>"

    s = run(puzzles, first_only)["summary"]
    one_movers = sum(len(p.positions) == 1 for p in puzzles)
    assert s["solve"]["value"] == pytest.approx(one_movers / 36)
    assert s["move_acc"]["value"] == pytest.approx(36 / s["positions"])


def test_engine_answers_dont_need_think(puzzles):
    eng = Profile(name="rnd", backend="random", seed=1)
    res = harness.run(harness.EvalRun(eng, "dev500", puzzles), RandomBackend(eng))
    assert res["summary"]["format"]["value"] == 1.0 and res["summary"]["legal"]["value"] == 1.0
    again = harness.run(harness.EvalRun(eng, "dev500", puzzles), RandomBackend(eng))
    assert [i["samples"][0]["san"] for i in res["items"]] == [
        i["samples"][0]["san"] for i in again["items"]
    ]


def test_cost_cap_stops_and_drops_partial_puzzles(puzzles, monkeypatch):
    monkeypatch.setattr(harness, "CHUNK", 10)
    sol = _solutions(puzzles)
    fake = Fake(lambda r: f"<think>x</think><answer>{sol[r.id]}</answer>", usd_per_call=0.01)
    res = run(puzzles, fake, max_usd=0.15)
    assert res["header"]["stopped"] and fake.calls == 20
    graded = {it["puzzle_id"] for it in res["items"]}
    for p in puzzles:
        if p.id in graded:
            assert sum(it["puzzle_id"] == p.id for it in res["items"]) == len(p.positions)
    assert res["summary"]["solve"]["value"] == 1.0


def test_pass_at_k(puzzles):
    sol = _solutions(puzzles)
    res = run(puzzles, lambda r: f"<think>x</think><answer>{sol[r.id]}</answer>", n=8)
    assert res["summary"]["pass_at"] == {"1": 1.0, "4": 1.0, "8": 1.0}


def test_compare_is_paired(puzzles):
    sol = _solutions(puzzles)
    good = run(puzzles, lambda r: f"<think>x</think><answer>{sol[r.id]}</answer>")
    bad = run(puzzles, lambda r: "<answer>Zz9</answer>")
    d = harness.compare(good, bad)
    assert d.value == 1.0 and d.lo == 1.0


def test_report_roundtrip(puzzles, tmp_path: Path, monkeypatch):
    sol = _solutions(puzzles)
    res = run(puzzles, lambda r: f"<think>x</think><answer>{sol[r.id]}</answer>")
    jp, md = report.write(res, tmp_path)
    assert jp.name == "fake-llm.json" and report.read(jp)["summary"] == res["summary"]
    text = md.read_text()
    assert "| solve rate | 100.0% [100.0, 100.0] |" in text and "## Examples" in text
    monkeypatch.setattr(report, "GZIP_OVER_BYTES", 10)
    jp2, _ = report.write(res, tmp_path)
    assert jp2.suffix == ".gz" and not jp.exists()
    assert report.read(jp2)["header"] == res["header"]


def test_profiles_in_repo_load():
    names = [p.stem for p in Path("configs/models").glob("*.yaml")]
    assert {"random", "stockfish-1node", "stockfish-1k", "qwen3-1.7b"} <= set(names)
    for n in names:
        p = load(n)
        assert p.name == n
        if p.backend == "vllm":
            assert p.hf_repo and p.revision and len(p.revision) == 40
        if p.backend == "gemini":
            assert p.vertex_model


# --- probe (E0) ------------------------------------------------------------------


def test_probe_grading():
    assert probe.grade("P1", "white knight", "<answer>White Knight.</answer>")["exact"] == 1.0
    assert probe.grade("P1", "empty", "x</think>\n`empty`")["exact"] == 1.0
    assert probe.grade("P1", "empty", "The square is empty")["exact"] == 0.0
    g = probe.grade("P2", "3: Ka1, Kb1, Kb2", "3: Ka1, Kb2, Kc3")
    assert g["exact"] == 1.0 and g["f1"] == pytest.approx(2 / 3)
    assert probe.grade("P2", "3: Ka1, Kb1, Kb2", "4: Ka1, Kb1, Kb2")["exact"] == 0.0
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert probe.grade("P3", fen, f"FEN: {fen.split()[0]} b KQkq e3 0 1")["exact"] == 1.0
    assert probe.grade("P3", fen, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w")["exact"] == 0.0
    assert probe.grade("P4", "yes, by Qe7", "Yes, by the queen")["exact"] == 1.0
    assert probe.grade("P4", "no", "No.")["exact"] == 1.0
    assert probe.grade("P4", "no", "yes")["exact"] == 0.0


def test_probe_reference_answers_grade_perfect():
    rows = sets.load_probe().to_dicts()
    assert len(rows) == 500
    for r in rows:
        g = probe.grade(r["task"], r["answer"], r["answer"])
        assert g["exact"] == 1.0, r
        if r["task"] == "P2":
            assert g["f1"] == 1.0


def test_probe_run_and_markdown(tmp_path: Path):
    rows = sets.spread(sets.load_probe().to_dicts(), 40)
    answers = {r["id"]: r["answer"] for r in rows}
    fake = Fake(lambda r: f"<answer>{answers[r.id]}</answer>")
    res = probe.run(LLM, rows, fake)
    assert all(d["exact"]["value"] == 1.0 for d in res["summary"].values())
    msgs = probe.messages(rows[0])
    assert msgs[1]["content"].startswith("Position (FEN): ")
    assert "Legal moves" not in msgs[1]["content"]
    _, md = report.write(res, tmp_path, probe.markdown)
    assert "P3 FEN after move" in md.read_text()
    assert chess.Board(rows[0]["fen"])  # rows carry valid FENs


def test_template_closes_think_drops_the_think_requirement():
    assert LLM.require_think
    assert not LLM.model_copy(update={"template_closes_think": True}).require_think
    assert not Profile(name="sf", backend="stockfish", nodes=1).require_think
    assert not load("qwen3.5-2b").require_think and load("qwen3.5-2b-native").require_think


def test_rescore_regrades_format_only(puzzles):
    sol = _solutions(puzzles)
    res = run(puzzles, lambda r: f"<answer>{sol[r.id]}</answer>")  # no think block
    assert res["summary"]["format"]["value"] == 0.0 and res["summary"]["move_acc"]["value"] == 1.0
    closed = LLM.model_copy(update={"template_closes_think": True})
    new = harness.rescore(res, closed, "ADR-017")
    assert new["summary"]["format"]["value"] == 1.0
    assert new["summary"]["solve"] == res["summary"]["solve"]
    assert new["header"]["rescored"]["reason"] == "ADR-017"
    assert new["header"]["git_sha"] == res["header"]["git_sha"]
    assert "rescored" in report.markdown(new)
    with pytest.raises(ValueError, match="legal_list"):
        harness.rescore(res, closed.model_copy(update={"legal_list": False}), "x")


def test_rambling_after_the_answer_is_cut_and_not_truncated(puzzles):
    # ADR-022: an old output that answered and then ran to the cap grades as if it had stopped
    sol = _solutions(puzzles)
    res = run(puzzles, lambda r: f"<answer>{sol[r.id]}</answer> Step 1: <answer>Ka1</answer>")
    for it in res["items"]:
        it["samples"][0]["finish"] = "length"
    it = res["items"][0]
    it["samples"][0] |= {"text": "Let me think about the knight on", "finish": "length"}
    closed = LLM.model_copy(update={"template_closes_think": True})
    new = harness.rescore(res, closed, "ADR-022")
    s = new["summary"]
    assert s["truncated"] == pytest.approx(1 / s["positions"])
    assert s["format"]["value"] > 0.95 and s["move_acc"]["value"] < 1.0


def test_compare_counts_who_alone_solved_what(puzzles):
    from ks.eval import compare

    sol = _solutions(puzzles)
    good = run(puzzles, lambda r: f"<answer>{sol[r.id]}</answer>")
    bad = run(puzzles, lambda r: "<answer>Zz9</answer>")
    d = compare.paired(good, bad)
    assert d["n"] == 36 and d["a_only"] == 36 and d["b_only"] == 0
    assert d["delta"]["value"] == 1.0
    md = compare.markdown({"good": good, "bad": bad}, ref="bad")
    assert (
        "| good | 100.0% [100.0, 100.0] | +100.0" in md and "| 600-799 | 3 | 100.0% | 0.0% |" in md
    )
