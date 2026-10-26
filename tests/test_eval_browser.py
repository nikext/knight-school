from __future__ import annotations

import chess

from ks.eval import browser, sets


def _result(puzzles: list[sets.Puzzle], pick) -> dict:
    """A saved-result stand-in: answer pick(position) at every position, graded like the harness."""
    items = []
    for p in puzzles:
        for pos in p.positions:
            san = pick(pos)
            items.append(
                {
                    "id": f"{p.id}-{pos['ply']}",
                    "puzzle_id": p.id,
                    "rating": p.rating,
                    "bin": p.bin,
                    "ply": pos["ply"],
                    "fen": pos["fen"],
                    "is_last": pos["is_last"],
                    "samples": [
                        {
                            "text": f"<answer>{san}</answer>",
                            "san": san if san != "Zz9" else None,
                            "status": "ok" if san != "Zz9" else "illegal",
                            "correct": san == pos["solution_san"],
                        }
                    ],
                }
            )
    solved = [
        all(it["samples"][0]["correct"] for it in items if it["puzzle_id"] == p.id) for p in puzzles
    ]
    v = sum(solved) / len(solved)
    s = {"value": v, "lo": v, "hi": v}
    return {"items": items, "summary": {"solve": s, "move_acc": s, "legal": s}}


def test_build_joins_answers_and_checks_the_solve_rate() -> None:
    puzzles = sets.spread(sets.load_puzzles("dev500"), 12)
    rows = {p.id: {"Themes": "fork short", "FEN": "x", "Moves": "a b"} for p in puzzles}
    right = _result(puzzles, lambda pos: pos["solution_san"])
    wrong = _result(puzzles, lambda pos: "Zz9")
    results = {
        m.key: (right if m.key in ("primer", "stockfish") else wrong) for m in browser.MODELS
    }
    data = browser.build(results, puzzles, rows)

    keys = [m["key"] for m in data["models"]]
    assert keys == [m.key for m in browser.MODELS]
    assert data["models"][keys.index("primer")]["solve"]["value"] == 1.0
    assert len(data["bins"]) == sets.N_BINS
    p0, d0 = puzzles[0], data["puzzles"][0]
    assert d0["id"] == p0.id and d0["t"] == ["fork", "short"]
    assert d0["s"] == [0, 0, 1, 0, 1]
    assert len(d0["a"]) == len(p0.positions)
    shown, uci, ok = d0["a"][0][keys.index("primer")]
    assert (shown, uci, ok) == (p0.positions[0]["solution_san"], p0.positions[0]["solution_uci"], 1)
    assert d0["a"][0][keys.index("base")] == ["Zz9", None, 0]


def test_build_refuses_a_result_graded_on_other_positions() -> None:
    puzzles = sets.spread(sets.load_puzzles("dev500"), 3)
    rows = {p.id: {"Themes": "", "FEN": "x", "Moves": "a b"} for p in puzzles}
    r = _result(puzzles, lambda pos: pos["solution_san"])
    r["items"][0] = {**r["items"][0], "fen": chess.STARTING_FEN}
    try:
        browser.build({m.key: r for m in browser.MODELS}, puzzles, rows)
    except ValueError as e:
        assert "different position" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_shown_falls_back_to_the_raw_answer() -> None:
    assert browser._shown({"san": None, "text": "<answer> Qd4 </answer>"}) == "Qd4"
    assert browser._shown({"san": None, "text": ""}) == "—"
    assert browser._shown({"san": "Qxf7+", "text": "<answer>Qxf7+</answer>"}) == "Qxf7+"
