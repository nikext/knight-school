from __future__ import annotations

import random

import chess
import pytest

from ks.chess import board as kb
from ks.data import primer as pr

CASTLE = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
DOUBLE_CHECK = "4k3/8/8/1B6/8/8/8/4R1K1 b - - 0 1"  # Re1 and Bb5 both check e8
EP = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
PROMO = "8/1P5k/8/8/8/8/8/K7 w - - 0 1"


def pos(fen: str, **kw) -> pr.Pos:
    return pr.Pos(chess.Board(fen), "evaldb", **kw)


def rng(seed: int = 0) -> random.Random:
    return random.Random(seed)


def test_piece_list_order_and_pawns_as_squares():
    b = chess.Board()
    assert (
        pr.piece_list(b, chess.WHITE) == "Ke1 Qd1 Ra1 Rh1 Bc1 Bf1 Nb1 Ng1 a2 b2 c2 d2 e2 f2 g2 h2"
    )
    assert pr.piece_list(b, chess.BLACK).startswith("Ke8 Qd8 Ra8 Rh8 Bc8 Bf8 Nb8 Ng8 a7")
    assert pr.piece_list(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), chess.WHITE) == "Ke1"
    assert pr.piece_list(b, chess.WHITE, chess.SquareSet()) == "none"


def test_t1_square_answers():
    b = chess.Board()
    assert pr.square_text(b, chess.E1) == "white king"
    assert pr.square_text(b, chess.G8) == "black knight"
    assert pr.square_text(b, chess.E4) == "empty"
    for seed in range(20):
        item = pr.t1_square(pos(chess.STARTING_FEN), rng(seed))
        sq = chess.parse_square(item.question.split()[-1].rstrip("?"))
        assert item.answer == pr.square_text(b, sq)


def test_t2_all_matches_python_chess():
    item = pr.t2_all(pos(chess.STARTING_FEN), rng())
    assert item.answer.startswith("20: Na3, Nc3, Nf3, Nh3, a3, a4, b3")
    count, moves = item.answer.split(": ")
    b = chess.Board()
    assert int(count) == b.legal_moves.count()
    assert moves.split(", ") == kb.legal_san(b)


def test_t2_piece_lists_that_pieces_moves_or_none():
    for seed in range(30):
        item = pr.t2_piece(pos(CASTLE), rng(seed))
        assert item is not None
        sq = chess.parse_square(item.question.split()[-1].rstrip("?"))
        b = chess.Board(CASTLE)
        want = kb.sort_san(b.san(m) for m in b.legal_moves if m.from_square == sq)
        assert item.answer == (", ".join(want) if want else "none")
    king = [pr.t2_piece(pos(CASTLE), rng(s)) for s in range(60)]
    e1 = [i for i in king if i and i.question.endswith("e1?")]
    assert e1 and "O-O" in e1[0].answer and "O-O-O" in e1[0].answer


@pytest.mark.parametrize("fen", [CASTLE, EP, PROMO, chess.STARTING_FEN])
def test_t3_answer_is_the_fen_after_the_move(fen):
    for seed in range(10):
        item = pr.t3_effect(pos(fen), rng(seed))
        assert item is not None
        b = chess.Board(fen)
        b.push_san(item.move)
        assert item.answer == b.fen()
        assert item.question == f"FEN after {item.move}?"
        assert item.keys() == [kb.key(chess.Board(fen)), kb.key(b)]


def test_t3_oversamples_special_moves():
    moves = {pr.t3_effect(pos(CASTLE), rng(s)).move for s in range(200)}  # type: ignore[union-attr]
    assert {"O-O", "O-O-O"} <= moves
    ep = {pr.t3_effect(pos(EP), rng(s)).move for s in range(200)}  # type: ignore[union-attr]
    assert "exf6" in ep


def test_castling_fen_by_hand():
    b = chess.Board(CASTLE)
    b.push_san("O-O")
    assert b.fen() == "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1"


def test_t4_check_single_double_and_none():
    assert pr.t4_check(pos(DOUBLE_CHECK), rng()).answer == "yes, by Re1 and Bb5"
    assert pr.t4_check(pos(chess.STARTING_FEN), rng()).answer == "no"
    pawn = "4k3/3P4/8/8/8/8/8/4K3 b - - 0 1"
    assert pr.t4_check(pos(pawn), rng()).answer == "yes, by d7"


def test_t4_attackers_and_captures():
    for seed in range(20):
        item = pr.t4_attackers(pos(EP), rng(seed))
        words = item.question.split()
        color = chess.WHITE if words[1] == "White" else chess.BLACK
        sq = chess.parse_square(words[-1].rstrip("?"))
        b = chess.Board(EP)
        assert item.answer == pr.piece_list(b, color, b.attackers(color, sq))
    assert pr.t4_captures(pos(EP), rng()).answer == "exf6"
    assert pr.t4_captures(pos(chess.STARTING_FEN), rng()).answer == "none"


def test_t5_from_engine_pv_with_960_castling_and_from_a_puzzle():
    item = pr.t5_best(pos(CASTLE, line=["e1h1", "e8a8"]), rng())
    assert item is not None and item.answer == "O-O" and item.legal
    prompt = item.record("x", "evaldb")["messages"][1]["content"]
    assert "Legal moves: " in prompt and prompt.endswith("Best move?")
    puzzle = pr.Pos(chess.Board(CASTLE), "puzzle", solution_san="Rxa8+")
    assert pr.t5_best(puzzle, rng()).answer == "Rxa8+"  # type: ignore[union-attr]
    assert pr.t5_best(pos(CASTLE, line=[]), rng()) is None


def test_t8_is_t5_asked_with_the_rl_prompt():
    from ks.chess import prompt as kp
    from ks.chess.parse import parse

    item = pr.t5_best(pr.Pos(chess.Board(CASTLE), "puzzle", solution_san="Rxa8+"), rng())
    assert item is not None
    t5 = {**item.record("M-1", "puzzle"), "keys": item.keys()}
    rl = kp.user_text(kb.board_from_fen(t5["fen"]))
    t8 = pr.t8_from_t5(t5, rl, "M-T8-0000000")
    assert (t8["id"], t8["task"], t8["keys"], t8["fen"]) == (
        "M-T8-0000000",
        "T8",
        t5["keys"],
        CASTLE,
    )
    t5_user, t8_user = t5["messages"][1]["content"], t8["messages"][1]["content"]
    assert t8_user == kp.user_text(chess.Board(CASTLE))
    assert t5_user.splitlines()[:-1] == t8_user.splitlines()[:-2]  # only the instruction differs
    assert t8["messages"][0] == t5["messages"][0]
    answer = t8["messages"][2]["content"]
    assert answer == "<answer>Rxa8+</answer>"
    assert t5["messages"][2]["content"] == "Rxa8+"  # the T5 example is left as it was
    assert parse(answer, chess.Board(CASTLE)).san == "Rxa8+"


@pytest.mark.parametrize(
    ("cp", "mate", "want"),
    [
        (320, None, "White is winning (+3.2)"),
        (-45, None, "Equal (-0.5)"),
        (4, None, "Equal (0.0)"),
        (-4, None, "Equal (0.0)"),
        (149, None, "White is slightly better (+1.5)"),
        (-150, None, "Black is better (-1.5)"),
        (-300, None, "Black is winning (-3.0)"),
        (None, 3, "White mates in 3 (#3)"),
        (None, -2, "Black mates in 2 (#-2)"),
    ],
)
def test_eval_text(cp, mate, want):
    assert pr.eval_text(cp, mate) == want


def test_t6_turns_side_to_move_scores_into_whites_view():
    black_to_move = "4k3/8/8/8/8/8/8/4K3 b - - 0 1"
    assert pr.t6_eval(pos(black_to_move, cp=200), rng()).answer == "Black is better (-2.0)"  # type: ignore[union-attr]
    assert pr.t6_eval(pos(black_to_move, mate=1), rng()).answer == "Black mates in 1 (#-1)"  # type: ignore[union-attr]
    assert pr.t6_eval(pos(black_to_move), rng()) is None


def test_t7_best_line():
    item = pr.t7_line(pos(CASTLE, line=["e1h1", "e8a8", "a1a8", "c8d7"]), rng())
    assert item is not None and item.answer == "O-O O-O-O Ra8+"
    assert len(item.keys()) == 4
    mate_in_one = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    assert pr.t7_line(pos(mate_in_one, line=["d1d8"]), rng()).answer == "Rd8#"  # type: ignore[union-attr]
    assert pr.t7_line(pos(CASTLE, line=["e1h1"]), rng()) is None  # too short, no mate


def _sources(n: int = 400) -> tuple[pr.Source, pr.Source]:
    fens, lines = [], []
    b = chess.Board()
    r = random.Random(3)
    while len(fens) < n:
        if b.is_game_over():
            b = chess.Board()
        moves = list(b.legal_moves)
        b.push(r.choice(moves))
        if not b.is_game_over():
            fens.append(b.fen())
            lines.append(next(iter(b.legal_moves)).uci())
    ev = {"fen": fens, "cp": [10] * n, "mate": [None] * n, "line": lines}
    order = list(range(n))
    sols = [chess.Board(f).san(next(iter(chess.Board(f).legal_moves))) for f in fens]
    return pr.evaldb_source(ev, order), pr.puzzle_source(fens, sols)


def test_generate_never_emits_blocked_or_rl_positions_and_is_deterministic():
    ev, pz = _sources()
    blocked = {kb.key(chess.Board(f)) for f in [ev._make(i).board.fen() for i in range(0, 400, 3)]}  # type: ignore[union-attr]
    stats = pr.GenStats()
    out = list(pr.generate(150, ev, pz, frozenset(blocked), set(), 5, "T", stats))
    assert len(out) == 150
    assert stats.blocklist_drops > 0
    assert not any(k in blocked for ex in out for k in ex["keys"])
    assert all(ex["keys"][0] == kb.key(chess.Board(ex["fen"])) for ex in out)
    ev2, pz2 = _sources()
    again = list(pr.generate(150, ev2, pz2, frozenset(blocked), set(), 5, "T", pr.GenStats()))
    assert out == again
    msgs = out[0]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant"]
    assert msgs[0]["content"] == pr.SYSTEM
    assert msgs[1]["content"].startswith("Position (FEN): ")


def test_rules_weights_draw_only_t1_to_t4_in_primer_m_proportions():
    assert sum(pr.RULES_WEIGHTS.values()) == pytest.approx(1.0)
    m_share = sum(pr.WEIGHTS[t] for t in pr.RULES_WEIGHTS)
    for t, w in pr.RULES_WEIGHTS.items():
        assert w == pytest.approx(pr.WEIGHTS[t] / m_share)
    ev, pz = _sources()
    out = list(
        pr.generate(200, ev, pz, frozenset(), set(), 7, "R", pr.GenStats(), pr.RULES_WEIGHTS)
    )
    assert {ex["task"] for ex in out} == {"T1", "T2", "T3", "T4"}
    assert not any("Legal moves:" in ex["messages"][1]["content"] for ex in out)


def test_source_hands_out_each_position_once():
    ev, _ = _sources(50)
    seen = [ev.take().board.fen() for _ in range(20)]
    seen += [ev.take("check", pr.in_check).board.fen() for _ in range(0)]
    assert len(seen) == len(set(seen))
    with pytest.raises(RuntimeError, match="exhausted"):
        for _ in range(100):
            ev.take()


def test_shards_round_trip(tmp_path):
    exs = [{"id": f"x{i}", "v": i} for i in range(7)]
    paths, n = pr.write_shards(iter(exs), tmp_path / "S", shard_size=3)
    assert n == 7 and [p.name for p in paths] == [
        "shard-00000.jsonl.zst",
        "shard-00001.jsonl.zst",
        "shard-00002.jsonl.zst",
    ]
    assert list(pr.read_shards(paths)) == exs
