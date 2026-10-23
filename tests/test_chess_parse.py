from __future__ import annotations

import chess
import pytest

from ks.chess import parse as kp

START = chess.Board()
CASTLE = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
MATE_IN_1 = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")  # Ra8#
CHECK = chess.Board("4k3/8/8/8/8/8/3Q4/4K3 w - - 0 1")  # Qd7+, Qe2+, ...
PROMO = chess.Board("8/P6k/8/8/8/8/8/K7 w - - 0 1")  # a8=Q
TWO_KNIGHTS = chess.Board("4k3/8/8/8/8/8/8/1N2KN2 w - - 0 1")  # Nd2 is ambiguous: Nbd2 / Nfd2


def ans(move: str, think: str = "<think>ok</think>") -> str:
    return f"{think}\n<answer>{move}</answer>"


def test_plain_answer():
    p = kp.parse(ans("Nf3"), START)
    assert p.status == "ok" and p.san == "Nf3" and p.move == chess.Move.from_uci("g1f3")
    assert p.legal and p.well_formed(require_think=True)


@pytest.mark.parametrize(
    "text",
    [
        " Nf3 ",
        "**Nf3**",
        "`Nf3`",
        '"Nf3"',
        "Nf3.",
        "Nf3!",
        "Nf3!?",
        "1. Nf3",
        "1.Nf3",
        "\nNf3\n",
        "Nf3+",  # extra check sign
    ],
)
def test_tolerated_decorations(text: str):
    assert kp.parse(ans(text), START).san == "Nf3"


def test_missing_and_extra_mate_and_check_suffixes():
    assert kp.parse(ans("Ra8"), MATE_IN_1).san == "Ra8#"
    assert kp.parse(ans("Ra8#"), MATE_IN_1).san == "Ra8#"
    assert kp.parse(ans("Ra8+"), MATE_IN_1).san == "Ra8#"
    assert kp.parse(ans("Qd7"), CHECK).san == "Qd7+"


@pytest.mark.parametrize(("text", "san"), [("O-O", "O-O"), ("0-0", "O-O"), ("0-0-0", "O-O-O")])
def test_castling(text: str, san: str):
    assert kp.parse(ans(text), CASTLE).san == san


def test_black_move_number_with_dots():
    b = chess.Board()
    b.push_san("e4")
    assert kp.parse(ans("1... e5"), b).san == "e5"
    assert kp.parse(ans("1...e5"), b).san == "e5"


def test_promotion_needs_the_piece():
    assert kp.parse(ans("a8=Q"), PROMO).san == "a8=Q"
    assert kp.parse(ans("a8=N"), PROMO).san == "a8=N"
    assert kp.parse(ans("a8"), PROMO).status == "illegal"


def test_disambiguation_must_match_the_list():
    assert kp.parse(ans("Nbd2"), TWO_KNIGHTS).san == "Nbd2"
    assert kp.parse(ans("Nd2"), TWO_KNIGHTS).status == "illegal"  # ambiguous
    assert kp.parse(ans("Nbc3"), TWO_KNIGHTS).status == "illegal"  # over-disambiguated


@pytest.mark.parametrize("text", ["g1f3", "Ng1f3", "e2e4", "0000", "--"])
def test_long_algebraic_and_null_moves_are_not_from_the_list(text: str):
    assert not kp.parse(ans(text), START).legal


def test_illegal_and_unparseable():
    assert kp.parse(ans("Nf6"), START).status == "illegal"
    assert kp.parse(ans("Ke2"), START).status == "illegal"
    assert kp.parse(ans("the knight to f3"), START).status == "unparseable"
    assert kp.parse(ans("Nf3 Nc6"), START).status == "unparseable"
    assert kp.parse(ans(""), START).status == "unparseable"


def test_no_answer():
    p = kp.parse("<think>hmm</think> I play Nf3.", START)
    assert p.status == "no_answer" and not p.well_formed(require_think=False)
    assert kp.parse("<answer>Nf3", START).status == "no_answer"


def test_the_first_closed_answer_ends_the_response():
    # ADR-022: what a `</answer>` stop string would have generated
    p = kp.parse("<think>x</think><answer>e4</answer> no wait <answer>Nf3</answer>", START)
    assert p.san == "e4" and p.n_answers == 1
    assert p.well_formed(require_think=False)
    ramble = "<answer>Nf3</answer> Step 1: the knight " + "<answer>" * 3 + "x" * 4000
    assert kp.parse(ramble, START).well_formed(require_think=False)
    assert kp.cut(ramble) == "<answer>Nf3</answer>"
    assert kp.cut("no tags") == "no tags"


def test_stray_answer_tag_is_not_well_formed():
    p = kp.parse("<think>x</think><answer> <answer>Nf3</answer>", START)
    assert p.stray_tags and not p.well_formed(require_think=False)
    p = kp.parse("<think>x</think></answer><answer>Nf3</answer>", START)
    assert p.status == "no_answer" and p.stray_tags


def test_think_rules():
    assert kp.parse(ans("Nf3"), START).think_ok
    # native thinking: the opening tag is in the prompt
    assert kp.parse("reasoning...</think>\n<answer>Nf3</answer>", START).think_ok
    no_think = kp.parse("<answer>Nf3</answer>", START)
    assert no_think.legal and not no_think.think_ok
    assert no_think.well_formed(require_think=False)
    assert not no_think.well_formed(require_think=True)
    # answer inside the think block
    assert not kp.parse("<think><answer>Nf3</answer></think>", START).think_ok
    # two think blocks, or reversed tags
    assert not kp.parse("<think>a</think><think>b</think><answer>Nf3</answer>", START).think_ok
    assert not kp.parse("</think>x<think><answer>Nf3</answer>", START).think_ok


def test_unclosed_think_with_answer_is_legal_but_not_well_formed():
    p = kp.parse("<think>long reasoning cut off <answer>Nf3</answer>", START)
    assert p.legal and not p.think_ok


def test_legal_map_can_be_reused():
    legal = kp.legal_map(START)
    assert len(legal) == 20
    assert kp.parse(ans("e4"), START, legal).san == "e4"
