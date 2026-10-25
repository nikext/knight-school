"""Eval-DB parsing, reward-table post-processing, the blocklist and manifests."""

from __future__ import annotations

import json

import chess
import polars as pl
import pytest

from ks.chess import board as kb
from ks.data import blocklist as bl
from ks.data import evaldb, rewards
from ks.data import manifest as mf

BLACK_TO_MOVE = (
    '{"fen":"7r/1p3k2/p1bPR3/5p2/2B2P1p/8/PP4P1/3K4 b - -","evals":['
    '{"pvs":[{"cp":69,"line":"f7g7 e6e2"},{"cp":163,"line":"h8d8 d1e1"}],"knodes":4189,"depth":46},'
    '{"pvs":[{"cp":80,"line":"h8d8 d1e1"}],"knodes":10,"depth":20}]}'
)


def test_evaldb_parse_takes_deepest_first_pv_and_flips_to_side_to_move():
    row = evaldb.parse(BLACK_TO_MOVE)
    assert row == {
        "fen": "7r/1p3k2/p1bPR3/5p2/2B2P1p/8/PP4P1/3K4 b - - 0 1",
        "cp": -69,
        "mate": None,
        "line": "f7g7 e6e2",
        "depth": 46,
        "knodes": 4189,
    }
    white_mate = '{"fen":"6k1/6p1/8/4K3/4NN2/8/8/8 w - -","evals":[{"pvs":[{"mate":15,"line":"e5e6"}],"depth":95}]}'
    assert evaldb.parse(white_mate)["mate"] == 15  # type: ignore[index]
    assert evaldb.parse('{"fen":"8/8/8/8/8/8/8/K6k w - -","evals":[]}') is None


def test_reservoir_is_seeded_and_bounded():
    lines = [BLACK_TO_MOVE] * 1000
    a, n = evaldb.reservoir(iter(lines), 10, 500, seed=1)
    b, _ = evaldb.reservoir(iter(lines), 10, 500, seed=1)
    c, _ = evaldb.reservoir(iter(lines), 10, 500, seed=2)
    assert n == 500 and len(a) == 10
    assert [i for i, _ in a] == [i for i, _ in b] != [i for i, _ in c]
    assert all(i <= 500 for i, _ in a)
    assert evaldb.to_frame(a).height == 10


def _table(rows):
    return pl.DataFrame(rows)


def test_agreement_and_mismatch_filter():
    df = _table(
        [
            # agrees
            {
                "legal_san": ["a", "b"],
                "solution_san": "a",
                "sf_best_san": "a",
                "wp": [0.9, 0.5],
                "mate": [None, None],
            },
            # disagrees by 0.1: kept
            {
                "legal_san": ["a", "b"],
                "solution_san": "b",
                "sf_best_san": "a",
                "wp": [0.9, 0.8],
                "mate": [None, None],
            },
            # disagrees by 0.4: dropped
            {
                "legal_san": ["a", "b"],
                "solution_san": "b",
                "sf_best_san": "a",
                "wp": [0.9, 0.5],
                "mate": [None, None],
            },
            # two different mates: both_mate, kept
            {
                "legal_san": ["a", "b"],
                "solution_san": "b",
                "sf_best_san": "a",
                "wp": [1.0, 1.0],
                "mate": [2, 3],
            },
        ]
    )
    out = rewards.agreement(df)
    assert out["sf_agrees"].to_list() == [True, False, False, False]
    assert out["both_mate"].to_list() == [False, False, False, True]
    kept, dropped = rewards.mismatch_filter(out)
    assert dropped == 1 and kept.height == 3


def test_shard_seconds_accumulate_across_runs(tmp_path):
    assert rewards.shard_seconds(tmp_path) == {}
    rewards._record_secs(tmp_path, "shard-0000.parquet", 12.34)
    rewards._record_secs(tmp_path, "shard-0001.parquet", 5.0)
    assert rewards.shard_seconds(tmp_path) == {
        "shard-0000.parquet": 12.3,
        "shard-0001.parquet": 5.0,
    }


def test_blocklist_round_trip_and_hits(tmp_path):
    fen = "r6k/pp2r2p/4Rp1Q/3p4/8/1N1P2R1/PqP2bPP/7K b - - 0 24"
    keys = bl.puzzle_keys(pl.DataFrame([{"FEN": fen, "Moves": "f2g3 e6e7"}]))
    assert len(keys) == 3
    bl.write(tmp_path, keys, ["787zsVup"])
    block = bl.Blocklist.load(tmp_path)
    assert block.games == {"787zsVup"}
    b = chess.Board(fen)
    assert block.hit(b)
    b.push_uci("f2g3")
    # Same position with different move counters is still a hit.
    assert block.hits_fens([b.fen(), b.fen().rsplit(" ", 2)[0] + " 0 1", chess.STARTING_FEN]) == 2


def test_probe_keys_include_the_position_after_the_move():
    df = pl.DataFrame(
        [
            {"fen": chess.STARTING_FEN, "move": "e4"},
            {"fen": "4k3/8/8/8/8/8/8/4K3 w - - 0 1", "move": ""},
        ]
    )
    after = chess.Board()
    after.push_san("e4")
    keys = bl.probe_keys(df)
    assert keys == {kb.key(chess.Board()), kb.key(after), "4k3/8/8/8/8/8/8/4K3 w - -"}


def test_manifest_skip_logic(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "MANIFESTS", tmp_path / "manifests")
    monkeypatch.setattr(mf, "rel", lambda p: str(p))
    out = tmp_path / "x.txt"
    out.write_text("hello")
    mf.write("x", "fp1", [out], rows=1)
    assert mf.up_to_date("x", "fp1", [out])
    assert not mf.up_to_date("x", "fp2", [out])
    out.write_text("changed")
    assert not mf.up_to_date("x", "fp1", [out])
    d = tmp_path / "shards"
    d.mkdir()
    (d / "a").write_text("1")
    (d / "b").write_text("2")
    mf.write("d", "fp", [d])
    assert mf.up_to_date("d", "fp", [d])
    (d / "b").write_text("3")
    assert not mf.up_to_date("d", "fp", [d])


# --- committed artefacts (CI) -------------------------------------------------------------

TRAINING_MANIFESTS = [
    "rl_train_candidates",
    "rl_train",
    "primer_S",
    "primer_M",
    "primer_M-t8",
    "primer_rules-M",
    "primer_S-t8",
    "primer_rules-M-t9",
    "primer_rules-M-t9-10",
]


def _manifests() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in sorted(mf.MANIFESTS.glob("*.json"))}


def test_every_committed_manifest_has_zero_contamination_hits():
    ms = _manifests()
    for name in TRAINING_MANIFESTS:
        assert name in ms, f"manifests/{name}.json is missing"
        assert "contamination_hits" in ms[name], name
    for name, m in ms.items():
        if "contamination_hits" in m:
            assert m["contamination_hits"] == 0, name


@pytest.fixture(scope="module")
def eval_sets() -> dict[str, pl.DataFrame]:
    def read(name: str) -> pl.DataFrame:
        return pl.read_csv(mf.SETS / f"{name}.csv", schema_overrides={"PuzzleId": pl.String})

    return {"test2000": read("test2000"), "dev500": read("dev500")}


def test_committed_eval_sets_are_split_by_game_and_stratified(eval_sets):
    from ks.data.puzzles import bin_quotas, game_id

    test, dev = eval_sets["test2000"], eval_sets["dev500"]
    assert test.height == 2000 and dev.height == 500
    tg, dg = {game_id(u) for u in test["GameUrl"]}, {game_id(u) for u in dev["GameUrl"]}
    assert len(tg) == 2000 and len(dg) == 500 and not tg & dg
    assert test.group_by("rating_bin").len().sort("rating_bin")["len"].to_list() == bin_quotas(2000)
    ids500 = (mf.SETS / "test500.ids").read_text().split()
    assert len(ids500) == 500 and set(ids500) <= set(test["PuzzleId"])
    block = bl.Blocklist.load(mf.SETS)
    assert tg | dg <= block.games


def test_committed_blocklist_covers_every_eval_position(eval_sets):
    block = bl.Blocklist.load(mf.SETS)
    for df in eval_sets.values():
        assert bl.puzzle_keys(df) <= block.keys
    probe = pl.read_csv(mf.SETS / "probe500.csv").with_columns(pl.col("move").fill_null(""))
    assert probe.height == 500
    assert bl.probe_keys(probe) <= block.keys
