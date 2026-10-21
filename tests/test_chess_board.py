from __future__ import annotations

import chess
import pytest

from ks.chess import board as kb

CASTLE = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
TWO_MATES = "6k1/5ppp/8/8/8/8/5PPP/R2R2K1 w - - 0 1"  # Ra8# and Rd8#


def test_key_keeps_ep_square_only_when_ep_capture_is_legal():
    legal_ep = chess.Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    assert kb.key(legal_ep) == "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6"
    no_capture = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq e6 0 2")
    assert kb.key(no_capture) == "rnbqkbnr/pppp1ppp/8/4p3/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def test_key_ignores_move_counters():
    a = chess.Board("8/8/8/4k3/8/8/8/4K2R w K - 0 1")
    b = chess.Board("8/8/8/4k3/8/8/8/4K2R w K - 37 90")
    assert kb.key(a) == kb.key(b)


def test_legal_san_order_is_code_point_order():
    sans = kb.legal_san(chess.Board(CASTLE))
    assert sans == sorted(sans)
    start = kb.legal_san(chess.Board())
    assert start[:4] == ["Na3", "Nc3", "Nf3", "Nh3"]
    assert start[-2:] == ["h3", "h4"]
    assert kb.sort_san(["exd5", "O-O", "a3", "Bb5", "Qe2", "Kf1", "Nf3"]) == [
        "Bb5",
        "Kf1",
        "Nf3",
        "O-O",
        "Qe2",
        "a3",
        "exd5",
    ]


def test_board_from_four_field_fen():
    b = kb.board_from_fen("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - -")
    assert b.fen() == "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"


def test_chess960_castling_in_pv_becomes_standard_moves_and_san():
    b = chess.Board(CASTLE)
    moves = kb.uci960_to_moves(b, ["e1h1", "e8a8", "a1a8"])
    assert [m.uci() for m in moves] == ["e1g1", "e8c8", "a1a8"]
    assert kb.pv_to_san(b, ["e1h1", "e8a8", "a1a8"]) == ["O-O", "O-O-O", "Ra8+"]


def test_pv_stops_at_first_illegal_or_garbage_move():
    b = chess.Board(CASTLE)
    assert kb.pv_to_san(b, ["e1h1", "e1g1"]) == ["O-O"]  # e1g1 after castling: king isn't there
    assert kb.pv_to_san(b, ["zz", "e1h1"]) == []
    # A standard-notation castle is not a legal Chess960 move, so it is not silently accepted.
    assert kb.pv_to_san(b, ["e1g1"]) == []


@pytest.mark.parametrize(
    ("cp", "mate", "want"),
    [
        (0, None, 0.5),
        (None, 3, 1.0),
        (None, -1, 0.0),
        (None, 0, 0.0),
    ],
)
def test_win_prob_fixed_points(cp, mate, want):
    assert kb.win_prob(cp, mate) == want


def test_win_prob_matches_lichess_and_clamps():
    # lila: 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1), in [0, 1] here
    assert kb.win_prob(100) == pytest.approx(0.5910, abs=1e-4)
    assert kb.win_prob(-100) == pytest.approx(1 - 0.5910, abs=1e-4)
    assert kb.win_prob(1000) == kb.win_prob(5000)
    assert kb.win_prob(-1000) == kb.win_prob(-5000)
    assert 0.97 < kb.win_prob(1000) < 0.98
    with pytest.raises(ValueError):
        kb.win_prob()


def test_alternative_mate_is_accepted_on_the_last_move_only():
    b = chess.Board(TWO_MATES)
    sol = b.parse_san("Rd8#")
    alt = b.parse_san("Ra8#")
    assert kb.solver_move_ok(b, sol, sol, is_last=True)
    assert kb.solver_move_ok(b, alt, sol, is_last=True)
    assert not kb.solver_move_ok(b, alt, sol, is_last=False)
    assert not kb.solver_move_ok(b, b.parse_san("Ra7"), sol, is_last=True)
    assert not kb.solver_move_ok(b, chess.Move.from_uci("a1h8"), sol, is_last=True)
