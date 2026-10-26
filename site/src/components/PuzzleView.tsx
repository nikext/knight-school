import { Chess, type Square } from "chess.js";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Chessboard, type Arrow } from "react-chessboard";
import type { BoardTheme, Mode } from "../App";
import { lineOf, MODEL_COLOR, moveNumber, solverAt, solverColor, tacticsFirst, themeName } from "../lib";
import type { Dataset, Puzzle } from "../types";
import {
  IconBulb,
  IconCheck,
  IconCross,
  IconExternal,
  IconEye,
  IconFirst,
  IconFlip,
  IconLast,
  IconNext,
  IconPrev,
  IconShuffle,
} from "./Icons";

interface Props {
  data: Dataset;
  puzzle: Puzzle;
  position: number;
  total: number;
  mode: Mode;
  setMode: (m: Mode) => void;
  boardTheme: BoardTheme;
  setBoardTheme: (t: BoardTheme) => void;
  onNext: () => void;
  onPrev: () => void;
  onRandom: () => void;
}

type Status = "turn" | "right" | "wrong" | "solved" | "revealed";

const BOARDS: Record<BoardTheme, { light: string; dark: string }> = {
  brown: { light: "#f0d9b5", dark: "#b58863" },
  blue: { light: "#dee3e6", dark: "#8ca2ad" },
  green: { light: "#ffffdd", dark: "#86a666" },
};

// Board marks follow the Lichess conventions.
const ARROW_GOOD = "#15781b";
const ARROW_BAD = "#c33";
const LAST_MOVE = "rgba(155, 199, 0, 0.41)";
const PICKED = "rgba(20, 85, 30, 0.5)";
const CHECK = "radial-gradient(ellipse at center, rgb(255,0,0) 0%, rgb(231,0,0) 25%, rgba(169,0,0,0) 89%, rgba(158,0,0,0) 100%)";
const DEST = "radial-gradient(rgba(20,85,30,0.5) 19%, rgba(0,0,0,0) 20%)";
const DEST_CAPTURE = "radial-gradient(transparent 0%, transparent 79%, rgba(20,85,30,0.3) 80%)";
const HINT = "rgba(21, 120, 27, 0.55)";
const WRONG = "rgba(204, 51, 51, 0.5)";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function kingSquare(g: Chess): Square | null {
  const turn = g.turn();
  for (const row of g.board()) for (const c of row) if (c && c.type === "k" && c.color === turn) return c.square;
  return null;
}

export default function PuzzleView(props: Props) {
  const { data, puzzle: p, position, total, mode, setMode, boardTheme, setBoardTheme, onNext, onPrev, onRandom } = props;
  const line = useMemo(() => lineOf(p), [p]);
  const n = p.m.length;
  const solver = solverColor(p);
  const nSolver = p.a.length;

  const [ply, setPly] = useState(0);
  const [flip, setFlip] = useState(false);
  const [sel, setSel] = useState("primer_rl");
  const [hover, setHover] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("turn");
  const [picked, setPicked] = useState<string | null>(null);
  const [mistakes, setMistakes] = useState(0);
  const [hint, setHint] = useState(false);
  const [wrongSq, setWrongSq] = useState<string | null>(null);
  const [finalFen, setFinalFen] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const solving = mode === "solve" && (status === "turn" || status === "right" || status === "wrong");
  const showAnswers = mode === "compare" || status === "solved" || status === "revealed";

  // Play the opponent's set-up move, as puzzle apps do.
  useEffect(() => {
    timer.current = window.setTimeout(() => setPly(1), 450);
    return () => window.clearTimeout(timer.current);
  }, []);

  const fen = finalFen && ply === n ? finalFen : line.fens[ply];
  const game = useMemo(() => new Chess(fen), [fen]);
  const { index: si } = solverAt(Math.max(ply, 1));
  const toMove = ply % 2 === 1 && ply < n;

  const goto = useCallback(
    (k: number) => {
      window.clearTimeout(timer.current);
      setPly(Math.max(0, Math.min(n, k)));
      setPicked(null);
    },
    [n],
  );

  const tryMove = useCallback(
    (from: string, to: string): boolean => {
      if (!solving || ply % 2 !== 1) return false;
      const sol = p.m[ply];
      const g = new Chess(line.fens[ply]);
      const promotion = from + to === sol.slice(0, 4) && sol[4] ? sol[4] : "q";
      let lan: string;
      try {
        lan = g.move({ from, to, promotion }).lan;
      } catch {
        return false;
      }
      setPicked(null);
      setHint(false);
      const last = ply === n - 1;
      // Like Lichess, any mate on the final move counts.
      if (lan !== sol && !(last && g.isCheckmate())) {
        setStatus("wrong");
        setMistakes((m) => m + 1);
        setWrongSq(to);
        return false;
      }
      setWrongSq(null);
      if (last) {
        if (lan !== sol) setFinalFen(g.fen());
        setPly(n);
        setStatus("solved");
        return true;
      }
      setStatus("right");
      setPly(ply + 1);
      timer.current = window.setTimeout(() => setPly(ply + 2), 500);
      return true;
    },
    [solving, ply, p, line, n],
  );

  const targets = useMemo(() => {
    if (!picked || !solving) return [];
    return game.moves({ square: picked as Square, verbose: true }).map((m) => ({ to: m.to, capture: !!m.captured }));
  }, [picked, solving, game]);

  // Board decorations
  const squareStyles = useMemo(() => {
    const s: Record<string, CSSProperties> = {};
    if (ply > 0 && !(finalFen && ply === n)) {
      const mv = line.moves[ply - 1];
      s[mv.from] = { background: LAST_MOVE };
      s[mv.to] = { background: LAST_MOVE };
    }
    if (game.inCheck()) {
      const k = kingSquare(game);
      if (k) s[k] = { ...s[k], backgroundImage: CHECK };
    }
    if (picked) s[picked] = { background: PICKED };
    for (const t of targets) s[t.to] = { ...s[t.to], backgroundImage: t.capture ? DEST_CAPTURE : DEST };
    if (hint && solving && toMove) s[p.m[ply].slice(0, 2)] = { background: HINT };
    if (wrongSq && status === "wrong") s[wrongSq] = { ...s[wrongSq], background: WRONG };
    return s;
  }, [ply, n, finalFen, line, game, picked, targets, hint, solving, toMove, p, wrongSq, status]);

  const shownKey = hover ?? sel;
  const arrows = useMemo<Arrow[]>(() => {
    if (!showAnswers || !toMove) return [];
    const sol = p.m[ply];
    const out: Arrow[] = [{ startSquare: sol.slice(0, 2), endSquare: sol.slice(2, 4), color: ARROW_GOOD }];
    const j = data.models.findIndex((m) => m.key === shownKey);
    const ans = j >= 0 ? p.a[si][j] : null;
    if (ans?.[1] && ans[1].slice(0, 4) !== sol.slice(0, 4)) {
      out.push({ startSquare: ans[1].slice(0, 2), endSquare: ans[1].slice(2, 4), color: ans[2] ? ARROW_GOOD : ARROW_BAD });
    }
    return out;
  }, [showAnswers, toMove, p, ply, si, data, shownKey]);

  // Keyboard: ← → step through the line, ↑ ↓ / j k change puzzle, f flips.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowRight" && !solving) goto(ply + 1);
      else if (e.key === "ArrowLeft" && !solving) goto(ply - 1);
      else if (e.key === "Home" && !solving) goto(0);
      else if (e.key === "End" && !solving) goto(n);
      else if (e.key === "ArrowDown" || e.key === "j") onNext();
      else if (e.key === "ArrowUp" || e.key === "k") onPrev();
      else if (e.key === "f") setFlip((x) => !x);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [solving, goto, ply, n, onNext, onPrev]);

  const theme = BOARDS[boardTheme];
  const orientation = flip ? (solver === "white" ? "black" : "white") : solver;
  const solutionSan = line.sans[2 * si + 1];

  return (
    <div className="puzzle">
      <section className="board-col" aria-label="Board">
        <div className={`board-wrap${status === "wrong" ? " shake" : ""}`}>
          <Chessboard
            options={{
              id: "ks-board",
              position: fen,
              boardOrientation: orientation,
              arrows,
              squareStyles,
              allowDrawingArrows: true,
              clearArrowsOnPositionChange: true,
              animationDurationInMs: 220,
              lightSquareStyle: { backgroundColor: theme.light },
              darkSquareStyle: { backgroundColor: theme.dark },
              lightSquareNotationStyle: { color: theme.dark, fontWeight: 600 },
              darkSquareNotationStyle: { color: theme.light, fontWeight: 600 },
              alphaNotationStyle: { fontSize: "clamp(9px, 1.6vw, 12px)", position: "absolute", bottom: 1, right: 3, userSelect: "none" },
              numericNotationStyle: { fontSize: "clamp(9px, 1.6vw, 12px)", position: "absolute", top: 2, left: 3, userSelect: "none" },
              boardStyle: { borderRadius: 6, overflow: "hidden", boxShadow: "var(--board-shadow)" },
              allowDragging: solving,
              canDragPiece: ({ piece }) => solving && toMove && piece.pieceType[0] === solver[0],
              onPieceDrop: ({ sourceSquare, targetSquare }) => (targetSquare ? tryMove(sourceSquare, targetSquare) : false),
              onSquareClick: ({ piece, square }) => {
                if (!solving || !toMove) return;
                if (picked && targets.some((t) => t.to === square)) {
                  tryMove(picked, square);
                } else if (piece && piece.pieceType[0] === solver[0]) {
                  setPicked(square === picked ? null : square);
                } else setPicked(null);
              },
            }}
          />
        </div>

        <div className="board-bar">
          <div className="seg" role="group" aria-label="Step through the line">
            <button className="icon-btn" onClick={() => goto(0)} disabled={solving || ply === 0} aria-label="First position" title="First (Home)">
              <IconFirst />
            </button>
            <button className="icon-btn" onClick={() => goto(ply - 1)} disabled={solving || ply === 0} aria-label="Previous move" title="Previous (←)">
              <IconPrev />
            </button>
            <button className="icon-btn" onClick={() => goto(ply + 1)} disabled={solving || ply === n} aria-label="Next move" title="Next (→)">
              <IconNext />
            </button>
            <button className="icon-btn" onClick={() => goto(n)} disabled={solving || ply === n} aria-label="Last position" title="Last (End)">
              <IconLast />
            </button>
          </div>
          <div className="board-tools">
            <div className="board-themes" role="radiogroup" aria-label="Board colours">
              {(Object.keys(BOARDS) as BoardTheme[]).map((t) => (
                <button
                  key={t}
                  role="radio"
                  aria-checked={boardTheme === t}
                  aria-label={`${cap(t)} board`}
                  title={`${cap(t)} board`}
                  className={`board-swatch${boardTheme === t ? " on" : ""}`}
                  style={{ background: `linear-gradient(135deg, ${BOARDS[t].light} 50%, ${BOARDS[t].dark} 50%)` }}
                  onClick={() => setBoardTheme(t)}
                />
              ))}
            </div>
            <button className="icon-btn" onClick={() => setFlip((x) => !x)} aria-label="Flip board" title="Flip board (f)">
              <IconFlip />
            </button>
          </div>
        </div>
      </section>

      <section className="panel" aria-label="Puzzle details">
        <div className="card head-card">
          <div className="head-top">
            <div>
              <div className="eyebrow">
                Puzzle {position >= 0 ? `${(position + 1).toLocaleString()} of ${total.toLocaleString()}` : "(outside the filter)"}
              </div>
              <h1 className="puzzle-title">
                #{p.id}
                <a className="lichess-link" href={`https://lichess.org/training/${p.id}`} target="_blank" rel="noreferrer" title="Open on Lichess">
                  Lichess <IconExternal width={14} height={14} />
                </a>
              </h1>
            </div>
            <div className="rating" title="Lichess puzzle rating">
              <span className="rating-num">{p.r}</span>
              <span className="rating-label">rating</span>
            </div>
          </div>
          <div className="chips">
            {tacticsFirst(p.t).map((t) => (
              <span key={t} className="chip">
                {themeName(t)}
              </span>
            ))}
          </div>
          <div className="segmented" role="tablist" aria-label="Mode">
            <button role="tab" aria-selected={mode === "compare"} className={mode === "compare" ? "on" : ""} onClick={() => setMode("compare")}>
              Compare models
            </button>
            <button role="tab" aria-selected={mode === "solve"} className={mode === "solve" ? "on" : ""} onClick={() => setMode("solve")}>
              Solve it yourself
            </button>
          </div>
        </div>

        {mode === "solve" && (
          <div className={`card turn-card turn-${status}`} aria-live="polite">
            <span className={`turn-piece ${solver}`} aria-hidden="true">
              {status === "solved" ? <IconCheck width={28} height={28} /> : status === "wrong" ? <IconCross width={28} height={28} /> : "♚"}
            </span>
            <div className="turn-text">
              {status === "turn" && (
                <>
                  <strong>Your turn</strong>
                  <span>Find the best move for {cap(solver)}.</span>
                </>
              )}
              {status === "right" && (
                <>
                  <strong>Best move!</strong>
                  <span>Keep going…</span>
                </>
              )}
              {status === "wrong" && (
                <>
                  <strong>That's not the move</strong>
                  <span>Try something else.</span>
                </>
              )}
              {status === "solved" && (
                <>
                  <strong>{mistakes ? "Solved, with " + mistakes + (mistakes === 1 ? " mistake" : " mistakes") : "Success!"}</strong>
                  <span>See how the models did below.</span>
                </>
              )}
              {status === "revealed" && (
                <>
                  <strong>Solution shown</strong>
                  <span>Step through it with ← →.</span>
                </>
              )}
            </div>
            <div className="turn-actions">
              {solving ? (
                <>
                  <button className="btn ghost" onClick={() => setHint(true)} disabled={!toMove || hint}>
                    <IconBulb /> Hint
                  </button>
                  <button
                    className="btn ghost"
                    onClick={() => {
                      window.clearTimeout(timer.current);
                      setStatus("revealed");
                      setPicked(null);
                    }}
                  >
                    <IconEye /> Solution
                  </button>
                </>
              ) : (
                <button className="btn primary" onClick={onNext}>
                  Next puzzle <IconNext />
                </button>
              )}
            </div>
          </div>
        )}

        {showAnswers && (
          <div className="card answers">
            <div className="answers-head">
              <h2>
                Move {si + 1} of {nSolver}
                <span className="muted"> · {cap(solver)} to play</span>
              </h2>
              {nSolver > 1 && (
                <div className="pips" aria-hidden="true">
                  {p.a.map((_, i) => (
                    <button key={i} className={`pip${i === si ? " on" : ""}`} onClick={() => goto(2 * i + 1)} tabIndex={-1} />
                  ))}
                </div>
              )}
            </div>
            <div className="solution-row">
              <span className="sol-label">Solution</span>
              <span className="san strong">{solutionSan}</span>
            </div>
            <ul className="model-rows" onMouseLeave={() => setHover(null)}>
              {data.models.map((m, j) => {
                const [shown, uci, ok] = p.a[si][j];
                const verdict = ok ? "right" : uci ? "wrong" : "illegal";
                return (
                  <li key={m.key}>
                    <button
                      className={`model-row${sel === m.key ? " on" : ""}`}
                      onClick={() => setSel(m.key)}
                      onMouseEnter={() => setHover(m.key)}
                      onFocus={() => setHover(m.key)}
                      onBlur={() => setHover(null)}
                      aria-pressed={sel === m.key}
                      title={m.blurb}
                    >
                      <span className="swatch" style={{ background: MODEL_COLOR[m.key] }} />
                      <span className="model-name">
                        {m.label}
                        {m.key === "stockfish" && <span className="tag">engine</span>}
                      </span>
                      <span className={`san${ok ? "" : " miss"}`}>{shown}</span>
                      <span className={`verdict ${verdict}`}>
                        {ok ? <IconCheck width={14} height={14} /> : <IconCross width={14} height={14} />}
                        {verdict}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className="hint-text">
              {toMove ? "Hover or pick a model to draw its move. Green = solution, red = a wrong move." : "Step back to this move's position (←) to see the arrows."}
            </p>
            <div className="whole">
              <span className="sol-label">Whole puzzle</span>
              <div className="whole-chips">
                {data.models.map((m, j) => (
                  <span key={m.key} className={`whole-chip ${p.s[j] ? "yes" : "no"}`} title={`${m.label}: ${p.s[j] ? "every move right" : "missed at least one move"}`}>
                    {p.s[j] ? <IconCheck width={12} height={12} /> : <IconCross width={12} height={12} />}
                    {m.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="card">
          <h2 className="card-title">Moves</h2>
          <ol className="movelist">
            {line.sans.map((san, k) => {
              const visible = !solving || k < ply;
              const isSolver = k % 2 === 1;
              return (
                <li key={k}>
                  <button
                    className={`mv${ply === k + 1 ? " on" : ""}${isSolver ? " solver" : ""}`}
                    disabled={solving}
                    onClick={() => goto(k + 1)}
                  >
                    <span className="mv-num">{moveNumber(p, k)}</span>
                    <span className="mv-san">{visible ? san : "?"}</span>
                  </button>
                </li>
              );
            })}
          </ol>
          <p className="hint-text">The first move sets up the puzzle. The solver's moves are in bold.</p>
        </div>

        <div className="nav-row">
          <button className="btn" onClick={onPrev} title="Previous puzzle (↑ or k)">
            <IconPrev /> Prev
          </button>
          <button className="btn" onClick={onRandom} title="Random puzzle from the list">
            <IconShuffle /> Random
          </button>
          <button className="btn" onClick={onNext} title="Next puzzle (↓ or j)">
            Next <IconNext />
          </button>
        </div>
        <p className="kbd-help">
          <kbd>←</kbd> <kbd>→</kbd> moves · <kbd>↑</kbd> <kbd>↓</kbd> puzzles · <kbd>f</kbd> flip
        </p>
      </section>
    </div>
  );
}
