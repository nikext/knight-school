from __future__ import annotations

import random

import chess
import polars as pl
import pytest

from ks.data import blocklist as bl
from ks.data import puzzles as P

# The first rows of the Lichess puzzle CSV (2026-10 export).
P00008 = (
    "00008",
    "r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24",
    "f2g3 e6e7 b2b1 b3c1 b1c1 h6c1",
)
P0000D = (
    "0000D",
    "5rk1/1p3ppp/pq3b2/8/8/1P1Q1N2/P4PPP/3R2K1 w - - 2 27",
    "d3d6 f8d8 d6d8 f6d8",
)


def test_expand_applies_the_opponents_first_move():
    pos = P.expand(*P00008, rating=1811, themes="crushing")
    assert [p["ply"] for p in pos] == [1, 3, 5]
    first = chess.Board(P00008[1])
    first.push_uci("f2g3")
    assert pos[0]["fen"] == first.fen()
    assert pos[0]["fen"].split()[1] == "w"  # the solver is White after Black's Bxg3
    assert [p["solution_san"] for p in pos] == ["Rxe7", "Nc1", "Qxc1"]
    assert [p["solution_uci"] for p in pos] == ["e6e7", "b3c1", "h6c1"]
    assert [p["is_last"] for p in pos] == [False, False, True]
    assert pos[0]["legal_san"] == sorted(pos[0]["legal_san"])
    assert "Rxe7" in pos[0]["legal_san"]
    assert pos[0]["rating"] == 1811 and pos[0]["themes"] == "crushing"


def test_expand_follows_the_solution_and_the_reply():
    pos = P.expand(*P0000D)  # White's Qd6 sets it up; Black solves Rd8, Qxd8+, Bxd8
    b = chess.Board(P0000D[1])
    b.push_uci("d3d6")
    assert pos[0]["fen"] == b.fen() and pos[0]["solution_san"] == "Rd8"
    for uci in ["f8d8", "d6d8"]:
        b.push_uci(uci)
    assert pos[1]["fen"] == b.fen() and pos[1]["solution_san"] == "Bxd8"
    assert [p["is_last"] for p in pos] == [False, True]


def test_expand_rejects_an_illegal_solution():
    with pytest.raises(ValueError, match="illegal"):
        P.expand("x", P0000D[1], "d3d6 f8f1")


def test_line_keys_cover_every_position_on_the_line():
    keys = P.line_keys(P00008[1], P00008[2])
    assert len(keys) == 7  # start + 6 moves
    assert keys[1] == P.expand(*P00008)[0]["key"]


def test_game_id_and_rating_bins():
    assert P.game_id("https://lichess.org/787zsVup/black#48") == "787zsVup"
    assert P.game_id("https://lichess.org/F8M8OS71#53") == "F8M8OS71"
    assert [P.rating_bin(r) for r in [400, 599, 600, 2599, 2600, 2800]] == [0, 0, 1, 10, 11, 11]
    assert P.bin_quotas(2000) == [167] * 8 + [166] * 4
    assert P.bin_quotas(500) == [42] * 8 + [41] * 4
    assert sum(P.bin_quotas(66_000)) == 66_000


def _synthetic(n: int, seed: int) -> pl.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        game = f"g{rng.randrange(n // 2):05d}"  # about two puzzles per game
        rows.append(
            {
                "PuzzleId": f"p{i:05d}",
                "Rating": rng.randrange(400, 2801),
                "GameUrl": f"https://lichess.org/{game}#{i}",
            }
        )
    return pl.DataFrame(rows)


def test_splits_are_deterministic_for_a_seed_and_split_by_game():
    df = _synthetic(3000, 1)
    sizes = {"test": 120, "dev": 36}
    a, games_a = P.pick_eval_sets(P.with_split_columns(df, seed=7), sizes)
    b, games_b = P.pick_eval_sets(P.with_split_columns(df.reverse(), seed=7), sizes)
    c, _ = P.pick_eval_sets(P.with_split_columns(df, seed=8), sizes)
    assert a["test"]["PuzzleId"].to_list() == b["test"]["PuzzleId"].to_list()
    assert a["dev"]["PuzzleId"].to_list() == b["dev"]["PuzzleId"].to_list()
    assert games_a == games_b
    assert a["test"]["PuzzleId"].to_list() != c["test"]["PuzzleId"].to_list()
    test_games, dev_games = set(a["test"]["game_id"]), set(a["dev"]["game_id"])
    assert not test_games & dev_games
    assert len(test_games) == 120 and len(dev_games) == 36  # one puzzle per game
    assert a["test"].group_by("rating_bin").len().sort("rating_bin")["len"].to_list() == [10] * 12
    sub = P.stratified_subset(a["test"], 24)
    assert set(sub["PuzzleId"]) <= set(a["test"]["PuzzleId"])
    assert sub.group_by("rating_bin").len()["len"].to_list() == [2] * 12


def _puzzle_frame(rows: list[tuple[str, str, str]], game_prefix: str = "G") -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "PuzzleId": pid,
                "FEN": fen,
                "Moves": moves,
                "Rating": 1500,
                "Themes": "",
                "rating_bin": 0,
                "game_id": f"{game_prefix}{pid}",
            }
            for pid, fen, moves in rows
        ]
    )


def test_take_positions_drops_blocklisted_positions_and_games():
    test_set = pl.DataFrame([{"FEN": P00008[1], "Moves": P00008[2]}])
    blocked = bl.puzzle_keys(test_set)
    # Another game's puzzle whose solver position is on P00008's line (after Bxg3 Rxe7).
    start = chess.Board(P00008[1])
    start.push_uci("f2g3")
    clash = ("clash", start.fen(), "e6e7 b2b1")
    df = _puzzle_frame([clash, P0000D, ("skipme", P00008[1], P00008[2])])
    used, positions, stats = P.take_positions(
        df, target=2, blocked=blocked, blocked_games={"Gskipme"}, n_bins=1
    )
    assert stats["blocklist_hits_dropped"] == 1
    assert [p["puzzle_id"] for p in positions] == ["0000D", "0000D"]
    assert "skipme" not in used["PuzzleId"].to_list()
    assert all(p["key"] not in blocked for p in positions)


def test_take_positions_fails_loudly_when_a_bin_runs_dry():
    df = _puzzle_frame([P0000D])
    with pytest.raises(ValueError, match="only 2 of 5"):
        P.take_positions(df, target=5, blocked=set(), blocked_games=set(), n_bins=1)
