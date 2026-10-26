import { Chess, type Move } from "chess.js";
import type { Dataset, Filters, Puzzle, Want } from "./types";

export const RATING_MIN = 400;
export const RATING_MAX = 2800;

/** Series colours (dataviz reference palette, validated light and dark). Stockfish is a neutral reference. */
export const MODEL_COLOR: Record<string, string> = {
  primer_rl: "var(--series-1)",
  rl: "var(--series-2)",
  primer: "var(--series-3)",
  base: "var(--series-4)",
  stockfish: "var(--series-ref)",
};

export interface Line {
  /** fens[k]: position after k moves (fens[0] is the puzzle's FEN) */
  fens: string[];
  sans: string[];
  moves: Move[];
}

const lines = new Map<string, Line>();

/** Every position of the puzzle line, memoised per puzzle. */
export function lineOf(p: Puzzle): Line {
  const hit = lines.get(p.id);
  if (hit) return hit;
  const g = new Chess(p.fen);
  const fens = [g.fen()];
  const sans: string[] = [];
  const moves: Move[] = [];
  for (const u of p.m) {
    const mv = g.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] });
    moves.push(mv);
    sans.push(mv.san);
    fens.push(g.fen());
  }
  const line = { fens, sans, moves };
  lines.set(p.id, line);
  return line;
}

/** The solver position shown at `ply` (moves applied, 1..n) and whether its move has been played. */
export function solverAt(ply: number): { index: number; played: boolean } {
  const played = ply % 2 === 0;
  return { index: played ? ply / 2 - 1 : (ply - 1) / 2, played };
}

/** The colour the solver plays. The puzzle's FEN has the opponent to move. */
export function solverColor(p: Puzzle): "white" | "black" {
  return p.fen.split(" ")[1] === "w" ? "black" : "white";
}

/** Move number label for ply k of the line, e.g. "12." or "12…". */
export function moveNumber(p: Puzzle, k: number): string {
  const parts = p.fen.split(" ");
  const full = Number(parts[5]) || 1;
  const whiteFirst = parts[1] === "w";
  const half = k + (whiteFirst ? 0 : 1);
  const n = full + Math.floor(half / 2);
  return half % 2 === 0 ? `${n}.` : `${n}…`;
}

const THEME_NAMES: Record<string, string> = {
  mateIn1: "Mate in 1",
  mateIn2: "Mate in 2",
  mateIn3: "Mate in 3",
  mateIn4: "Mate in 4",
  mateIn5: "Mate in 5+",
  oneMove: "One move",
  short: "Short",
  long: "Long",
  veryLong: "Very long",
  crushing: "Crushing",
  advantage: "Advantage",
  equality: "Equality",
  middlegame: "Middlegame",
  endgame: "Endgame",
  opening: "Opening",
  kingsideAttack: "Kingside attack",
  queensideAttack: "Queenside attack",
  backRankMate: "Back-rank mate",
  hangingPiece: "Hanging piece",
  discoveredAttack: "Discovered attack",
  doubleCheck: "Double check",
  enPassant: "En passant",
  advancedPawn: "Advanced pawn",
  attackingF2F7: "Attacking f2/f7",
  capturingDefender: "Capture the defender",
  exposedKing: "Exposed king",
  trappedPiece: "Trapped piece",
  quietMove: "Quiet move",
  defensiveMove: "Defensive move",
  promotion: "Promotion",
  underPromotion: "Underpromotion",
  smotheredMate: "Smothered mate",
  master: "Master game",
  masterVsMaster: "Master vs master",
  superGM: "Super GM game",
};

export function themeName(t: string): string {
  if (THEME_NAMES[t]) return THEME_NAMES[t];
  const words = t.replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Themes that say something about the tactic (game phase and length tags are left out of the filter). */
const NOT_TACTICS = new Set(["short", "long", "veryLong", "oneMove", "crushing", "advantage", "equality", "master", "masterVsMaster", "superGM"]);

const PHASES = new Set(["opening", "middlegame", "endgame"]);

/** Themes ordered for display: tactics, then game phase, then length and evaluation tags. */
export function tacticsFirst(ts: string[]): string[] {
  const rank = (t: string) => (NOT_TACTICS.has(t) ? 2 : PHASES.has(t) ? 1 : 0);
  return [...ts].sort((a, b) => rank(a) - rank(b));
}

export function themeCounts(ps: Puzzle[]): [string, number][] {
  const c = new Map<string, number>();
  for (const p of ps) for (const t of p.t) if (!NOT_TACTICS.has(t)) c.set(t, (c.get(t) ?? 0) + 1);
  return [...c.entries()].sort((a, b) => b[1] - a[1]);
}

export function defaultFilters(keys: string[]): Filters {
  return {
    q: "",
    minR: RATING_MIN,
    maxR: RATING_MAX,
    theme: "",
    want: Object.fromEntries(keys.map((k) => [k, "any" as Want])),
    sort: "rating",
  };
}

export function applyFilters(d: Dataset, f: Filters): Puzzle[] {
  const q = f.q.trim().toLowerCase();
  const wants = d.models.map((m) => f.want[m.key] ?? "any");
  const out = d.puzzles.filter((p) => {
    if (p.r < f.minR || p.r > f.maxR) return false;
    if (f.theme && !p.t.includes(f.theme)) return false;
    for (let j = 0; j < wants.length; j++) {
      if (wants[j] === "yes" && !p.s[j]) return false;
      if (wants[j] === "no" && p.s[j]) return false;
    }
    if (q && !p.id.toLowerCase().includes(q) && !p.t.some((t) => themeName(t).toLowerCase().includes(q))) return false;
    return true;
  });
  const cmp: Record<Filters["sort"], (a: Puzzle, b: Puzzle) => number> = {
    rating: (a, b) => a.r - b.r || a.id.localeCompare(b.id),
    "-rating": (a, b) => b.r - a.r || a.id.localeCompare(b.id),
    id: (a, b) => a.id.localeCompare(b.id),
  };
  return out.sort(cmp[f.sort]);
}

/** Solve rate per model over a list of puzzles. */
export function solveRates(d: Dataset, ps: Puzzle[]): number[] {
  return d.models.map((_, j) => (ps.length ? ps.reduce((n, p) => n + p.s[j], 0) / ps.length : 0));
}

/** Solve rate per model per rating bin: rates[j][b]. */
export function binRates(d: Dataset): { n: number[]; rates: number[][] } {
  const n = d.bins.map(() => 0);
  const hits = d.models.map(() => d.bins.map(() => 0));
  for (const p of d.puzzles) {
    n[p.b]++;
    p.s.forEach((s, j) => (hits[j][p.b] += s));
  }
  return { n, rates: hits.map((row) => row.map((h, b) => (n[b] ? h / n[b] : 0))) };
}

export const PRESETS: { label: string; want: Record<string, Want> }[] = [
  { label: "All puzzles", want: {} },
  { label: "Primer → RL solved, Base → RL missed", want: { primer_rl: "yes", rl: "no" } },
  { label: "Base → RL solved, Primer → RL missed", want: { primer_rl: "no", rl: "yes" } },
  { label: "RL lost what the primer had", want: { primer: "yes", primer_rl: "no" } },
  { label: "Every LLM solved it", want: { base: "yes", rl: "yes", primer: "yes", primer_rl: "yes" } },
  { label: "No LLM solved it", want: { base: "no", rl: "no", primer: "no", primer_rl: "no" } },
  { label: "Stockfish missed it", want: { stockfish: "no" } },
];

export function pct(x: number, digits = 1): string {
  return `${(100 * x).toFixed(digits)}%`;
}
