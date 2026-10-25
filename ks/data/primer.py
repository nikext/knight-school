"""Teacher-free chess primer (DATA.md §7): tasks T1-T7, all answers from python-chess or Stockfish.

Answer formats are frozen here and shared with probe500 (EVALS.md §4), so a
primer checkpoint is graded in the format it was taught:

- pieces: `Ke1 Qd1 Ra1 Rh1 … a2 b2` (K Q R B N then pawns as bare squares,
  each group in square order a1, b1, …, h8), or `none`
- move lists: SAN in the frozen order (`ks.chess.board.sort_san`), joined by `, `
- squares: `white knight` / `empty`
- evaluation: White's point of view, e.g. `White is winning (+3.2)`, `Equal (-0.3)`,
  `Black mates in 2 (#-2)`
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import zstandard

from ks.chess import board as kb

SYSTEM = "You are a strong chess player solving a puzzle."  # same as the RL prompt (TRAINING.md §2)

COLOR = {chess.WHITE: "White", chess.BLACK: "Black"}
PIECE_ORDER = [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]

# Share of examples per task (by example count; M2 records tokens per task).
WEIGHTS = {"T1": 0.10, "T2": 0.15, "T3": 0.15, "T4": 0.10, "T5": 0.30, "T6": 0.10, "T7": 0.10}
# primer rules-M (E5a, ADR-028): T1-T4 only, in the proportions they have in primer-M. No answer
# is ever a move choice.
RULES_WEIGHTS = {"T1": 0.20, "T2": 0.30, "T3": 0.30, "T4": 0.20}
# T1-T5 draw half their positions from primer_pool puzzles, half from the eval DB.
# T6 and T7 need an engine score and PV, so they use the eval DB only.
PUZZLE_SHARE = 0.5
SPECIAL_MOVE_SHARE = 0.3  # T3 picks castling / ep / promotion this often when one is legal
EVAL_EQUAL, EVAL_SLIGHT, EVAL_BETTER = 50, 150, 300  # centipawn bucket edges, White's view


# --- formatting --------------------------------------------------------------------


def piece_token(piece_type: int, square: int) -> str:
    name = chess.square_name(square)
    return name if piece_type == chess.PAWN else chess.piece_symbol(piece_type).upper() + name


def piece_list(board: chess.Board, color: bool, mask: chess.SquareSet | None = None) -> str:
    toks = [
        piece_token(pt, sq)
        for pt in PIECE_ORDER
        for sq in board.pieces(pt, color)
        if mask is None or sq in mask
    ]
    return " ".join(toks) if toks else "none"


def move_list(sans: list[str]) -> str:
    return ", ".join(kb.sort_san(sans)) if sans else "none"


def square_text(board: chess.Board, square: int) -> str:
    p = board.piece_at(square)
    return "empty" if p is None else f"{COLOR[p.color].lower()} {chess.piece_name(p.piece_type)}"


def score_text(cp: int) -> str:
    """Centipawns as pawns with one decimal, rounding half away from zero; `0.0` has no sign."""
    tenths = (abs(cp) + 5) // 10
    if tenths == 0:
        return "0.0"
    return f"{'+' if cp > 0 else '-'}{tenths // 10}.{tenths % 10}"


def eval_text(cp: int | None, mate: int | None) -> str:
    """Bucket plus score, both from White's point of view."""
    if mate is not None:
        side = "White" if mate > 0 else "Black"
        return f"{side} mates in {abs(mate)} (#{mate})"
    assert cp is not None
    side = "White" if cp > 0 else "Black"
    a = abs(cp)
    if a < EVAL_EQUAL:
        bucket = "Equal"
    elif a < EVAL_SLIGHT:
        bucket = f"{side} is slightly better"
    elif a < EVAL_BETTER:
        bucket = f"{side} is better"
    else:
        bucket = f"{side} is winning"
    return f"{bucket} ({score_text(cp)})"


def user_prompt(board: chess.Board, question: str, legal: bool = False) -> str:
    lines = [f"Position (FEN): {board.fen()}", f"Side to move: {COLOR[board.turn]}"]
    if legal:
        lines.append(f"Legal moves: {', '.join(kb.legal_san(board))}")
    lines.append(question)
    return "\n".join(lines)


# --- items -------------------------------------------------------------------------


@dataclass
class Pos:
    """A source position. Eval-DB positions carry an engine score and PV, puzzle ones a solution."""

    board: chess.Board
    source: str  # "evaldb" | "puzzle"
    cp: int | None = None  # side to move
    mate: int | None = None  # side to move
    line: list[str] = field(default_factory=list)  # UCI_Chess960
    solution_san: str | None = None


@dataclass
class Item:
    task: str
    variant: str
    board: chess.Board
    question: str
    answer: str
    legal: bool = False  # show the legal-move line in the prompt
    move: str = ""  # T3: the SAN move applied
    after: list[chess.Board] = field(default_factory=list)  # boards the answer reveals

    def keys(self) -> list[str]:
        return [kb.key(self.board), *(kb.key(b) for b in self.after)]

    def record(self, ex_id: str, source: str) -> dict[str, Any]:
        return {
            "id": ex_id,
            "task": self.task,
            "variant": self.variant,
            "source": source,
            "fen": self.board.fen(),
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_prompt(self.board, self.question, self.legal)},
                {"role": "assistant", "content": self.answer},
            ],
        }


Rng = random.Random


def t1_square(pos: Pos, rng: Rng) -> Item:
    b = pos.board
    occupied = list(chess.SquareSet(b.occupied))
    sq = rng.choice(occupied) if rng.random() < 0.5 else rng.randrange(64)
    q = f"What is on {chess.square_name(sq)}?"
    return Item("T1", "square", b, q, square_text(b, sq))


def t1_pieces(pos: Pos, rng: Rng) -> Item:
    color = rng.choice([chess.WHITE, chess.BLACK])
    q = f"List {COLOR[color]}'s pieces."
    return Item("T1", "pieces", pos.board, q, piece_list(pos.board, color))


def t2_all(pos: Pos, rng: Rng) -> Item:
    sans = kb.legal_san(pos.board)
    q = "How many legal moves does the side to move have? List them."
    return Item("T2", "all", pos.board, q, f"{len(sans)}: {move_list(sans)}")


def t2_piece(pos: Pos, rng: Rng) -> Item | None:
    b = pos.board
    movers = sorted({m.from_square for m in b.legal_moves})
    own = list(chess.SquareSet(b.occupied_co[b.turn]))
    if not own:
        return None
    sq = rng.choice(movers) if movers and rng.random() < 0.8 else rng.choice(own)
    sans = [b.san(m) for m in b.legal_moves if m.from_square == sq]
    q = f"Legal moves of the piece on {chess.square_name(sq)}?"
    return Item("T2", "piece", b, q, move_list(sans))


def _special(b: chess.Board, m: chess.Move) -> bool:
    return b.is_castling(m) or b.is_en_passant(m) or m.promotion is not None


def t3_effect(pos: Pos, rng: Rng) -> Item | None:
    b = pos.board
    moves = list(b.legal_moves)
    if not moves:
        return None
    special = [m for m in moves if _special(b, m)]
    m = rng.choice(special) if special and rng.random() < SPECIAL_MOVE_SHARE else rng.choice(moves)
    san = b.san(m)
    after = b.copy(stack=False)
    after.push(m)
    return Item("T3", "effect", b, f"FEN after {san}?", after.fen(), move=san, after=[after])


def check_text(b: chess.Board) -> str:
    checkers = b.checkers()
    if not checkers:
        return "no"
    toks = [piece_list(b, not b.turn, checkers)]
    return "yes, by " + " and ".join(toks[0].split())


def t4_check(pos: Pos, rng: Rng) -> Item:
    return Item("T4", "check", pos.board, "Is the side to move in check?", check_text(pos.board))


def t4_attackers(pos: Pos, rng: Rng) -> Item:
    b = pos.board
    color = rng.choice([chess.WHITE, chess.BLACK])
    attacked = [sq for sq in chess.SQUARES if b.attackers(color, sq)]
    sq = rng.choice(attacked) if attacked and rng.random() < 0.8 else rng.randrange(64)
    q = f"Which {COLOR[color]} pieces attack {chess.square_name(sq)}?"
    return Item("T4", "attackers", b, q, piece_list(b, color, b.attackers(color, sq)))


def t4_captures(pos: Pos, rng: Rng) -> Item:
    b = pos.board
    sans = [b.san(m) for m in b.legal_moves if b.is_capture(m)]
    return Item("T4", "captures", b, "List all captures.", move_list(sans))


def _pv(pos: Pos) -> list[chess.Move]:
    return kb.uci960_to_moves(pos.board, pos.line)


def t5_best(pos: Pos, rng: Rng) -> Item | None:
    b = pos.board
    if pos.solution_san is not None:
        san = pos.solution_san
    else:
        pv = _pv(pos)
        if not pv:
            return None
        san = b.san(pv[0])
    after = b.copy(stack=False)
    after.push_san(san)
    return Item("T5", "best", b, "Best move?", san, legal=True, after=[after])


def t6_eval(pos: Pos, rng: Rng) -> Item | None:
    if pos.cp is None and pos.mate is None:
        return None
    sign = 1 if pos.board.turn == chess.WHITE else -1
    cp = None if pos.cp is None else sign * pos.cp
    mate = None if pos.mate is None else sign * pos.mate
    if mate == 0:
        return None
    return Item("T6", "eval", pos.board, "Who is better?", eval_text(cp, mate))


T7_PLIES = 3


def t7_line(pos: Pos, rng: Rng) -> Item | None:
    pv = _pv(pos)[:T7_PLIES]
    b = pos.board.copy(stack=False)
    sans: list[str] = []
    after: list[chess.Board] = []
    for m in pv:
        sans.append(b.san(m))
        b.push(m)
        after.append(b.copy(stack=False))
    if len(sans) < T7_PLIES and not (sans and sans[-1].endswith("#")):
        return None
    return Item("T7", "line", pos.board, "Best line, 3 moves?", " ".join(sans), after=after)


# T8 (TRAINING.md §5, ADR-024): the fallback for a primer that breaks the RL answer format. A
# copy of a T5 example asked with the RL prompt's instruction instead of "Best move?", answered
# with the same move in the RL answer tags. The caller renders the RL user turn
# (`ks.chess.prompt.user_text`, which imports this module).
T8_SHARE = 0.02  # of primer-M's example count


def t8_from_t5(t5: dict[str, Any], rl_user_text: str, ex_id: str) -> dict[str, Any]:
    system, _, answer = t5["messages"]
    return {
        **t5,
        "id": ex_id,
        "task": "T8",
        "variant": "rl-format",
        "messages": [
            system,
            {"role": "user", "content": rl_user_text},
            {"role": "assistant", "content": f"<answer>{answer['content']}</answer>"},
        ],
    }


Gen = Callable[[Pos, Rng], Item | None]
VARIANTS: dict[str, list[Gen]] = {
    "T1": [t1_square, t1_pieces],
    "T2": [t2_all, t2_piece],
    "T3": [t3_effect],
    "T4": [t4_check, t4_attackers, t4_captures],
    "T5": [t5_best],
    "T6": [t6_eval],
    "T7": [t7_line],
}
EVALDB_ONLY = {"T6", "T7"}


# --- sources -----------------------------------------------------------------------


class Source:
    """Positions handed out at most once each, in a fixed order; can skip to one that fits a test."""

    def __init__(self, make: Callable[[int], Pos | None], n: int) -> None:
        self._make, self._n = make, n
        self._used = bytearray(n)
        self._cursor: dict[str, int] = {}

    def take(self, want: str = "", pred: Callable[[Pos], bool] | None = None) -> Pos:
        i = self._cursor.get(want, 0)
        while i < self._n:
            if not self._used[i]:
                pos = self._make(i)
                if pos is None:
                    self._used[i] = 1
                elif pred is None or pred(pos):
                    self._used[i] = 1
                    self._cursor[want] = i + 1
                    return pos
            i += 1
        raise RuntimeError(f"source exhausted ({self._n} positions, want={want!r})")

    def used(self) -> int:
        return sum(self._used)


def playable(b: chess.Board) -> bool:
    return b.is_valid() and not b.is_game_over(claim_draw=False)


def evaldb_source(rows: dict[str, list[Any]], order: list[int]) -> Source:
    def make(i: int) -> Pos | None:
        r = order[i]
        b = kb.board_from_fen(rows["fen"][r])
        if not playable(b):
            return None
        return Pos(b, "evaldb", rows["cp"][r], rows["mate"][r], rows["line"][r].split())

    return Source(make, len(order))


def puzzle_source(fens: list[str], solutions: list[str]) -> Source:
    def make(i: int) -> Pos | None:
        b = chess.Board(fens[i])
        return Pos(b, "puzzle", solution_san=solutions[i]) if playable(b) else None

    return Source(make, len(fens))


def in_check(p: Pos) -> bool:
    return p.board.is_check()


# --- generation --------------------------------------------------------------------


@dataclass
class GenStats:
    per_task: dict[str, int] = field(default_factory=dict)
    per_source: dict[str, int] = field(default_factory=dict)
    blocklist_drops: int = 0
    rl_train_drops: int = 0
    skipped: int = 0


def generate(
    n: int,
    evaldb: Source,
    puzzle: Source,
    blocked: frozenset[str] | set[str],
    rl_keys: set[str],
    seed: int,
    prefix: str,
    stats: GenStats,
    weights: dict[str, float] = WEIGHTS,
) -> Iterator[dict[str, Any]]:
    """n examples in a seeded task order. Each source position is used at most once.

    An item is dropped when any position it shows or reveals is blocklisted
    (eval contamination) or is an rl_train position (keeps RL's contribution
    separable, RESEARCH.md H5); a fresh position is drawn instead.
    """
    rng = random.Random(seed)
    tasks, shares = list(weights), list(weights.values())
    i = 0
    while i < n:
        task = rng.choices(tasks, shares)[0]
        gen = rng.choice(VARIANTS[task])
        use_puzzle = task not in EVALDB_ONLY and rng.random() < PUZZLE_SHARE
        src = puzzle if use_puzzle else evaldb
        # Half of the check questions go to positions that are in check, else nearly all say "no".
        want_check = gen is t4_check and rng.random() < 0.5
        pos = src.take("check", in_check) if want_check else src.take()
        item = gen(pos, rng)
        if item is None:
            stats.skipped += 1
            continue
        keys = item.keys()
        if any(k in blocked for k in keys):
            stats.blocklist_drops += 1
            continue
        if any(k in rl_keys for k in keys):
            stats.rl_train_drops += 1
            continue
        stats.per_task[task] = stats.per_task.get(task, 0) + 1
        stats.per_source[pos.source] = stats.per_source.get(pos.source, 0) + 1
        yield item.record(f"{prefix}-{i:07d}", pos.source) | {"keys": keys}
        i += 1


def write_shards(
    examples: Iterator[dict[str, Any]], out_dir: Path, shard_size: int
) -> tuple[list[Path], int]:
    """zstd JSONL shards `shard-00000.jsonl.zst`, … Replaces whatever was in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("shard-*.jsonl.zst"):
        old.unlink()
    paths: list[Path] = []
    buf: list[str] = []
    total = 0

    def flush() -> None:
        p = out_dir / f"shard-{len(paths):05d}.jsonl.zst"
        p.write_bytes(zstandard.ZstdCompressor(level=10).compress("".join(buf).encode()))
        paths.append(p)
        buf.clear()

    for ex in examples:
        buf.append(json.dumps(ex, ensure_ascii=False) + "\n")
        total += 1
        if len(buf) >= shard_size:
            flush()
    if buf:
        flush()
    return paths, total


def read_shards(paths: list[Path]) -> Iterator[dict[str, Any]]:
    for p in sorted(paths):
        text = zstandard.ZstdDecompressor().decompressobj().decompress(p.read_bytes()).decode()
        for line in text.splitlines():
            yield json.loads(line)
