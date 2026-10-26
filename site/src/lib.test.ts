import { describe, expect, it } from "vitest";
import { applyFilters, binRates, defaultFilters, lineOf, moveNumber, solveRates, solverAt, solverColor, tacticsFirst, themeName } from "./lib";
import type { Dataset, Puzzle } from "./types";

// b3ic0 from test2000: Black's Rxe5 sets it up, White mates with Qxf7+ Kh8 Qf8#.
const mate2: Puzzle = {
  id: "b3ic0",
  r: 522,
  b: 0,
  t: ["kingsideAttack", "mate", "mateIn2", "middlegame", "short"],
  fen: "r1b1r1k1/pp3ppp/8/2p1R3/3p4/1BP2Q2/PPK2PP1/RNB2q2 b - - 0 18",
  m: ["e8e5", "f3f7", "g8h8", "f7f8"],
  s: [0, 0, 0, 0, 0],
  a: [],
};

function ds(ps: Puzzle[]): Dataset {
  const keys = ["base", "rl", "primer", "primer_rl", "stockfish"];
  const ci = { value: 0, lo: 0, hi: 0 };
  return {
    set: "test",
    bins: Array.from({ length: 12 }, (_, i) => `${400 + 200 * i}-${599 + 200 * i}`),
    models: keys.map((key) => ({ key, label: key, blurb: "", run: key, solve: ci, move_acc: 0, legal: 0 })),
    puzzles: ps,
  };
}

describe("puzzle line", () => {
  it("replays every move and names them in SAN", () => {
    const l = lineOf(mate2);
    expect(l.sans).toEqual(["Rxe5", "Qxf7+", "Kh8", "Qf8#"]);
    expect(l.fens).toHaveLength(5);
    expect(l.fens[0]).toBe(mate2.fen);
  });

  it("maps plies to solver positions", () => {
    expect(solverAt(1)).toEqual({ index: 0, played: false });
    expect(solverAt(2)).toEqual({ index: 0, played: true });
    expect(solverAt(3)).toEqual({ index: 1, played: false });
    expect(solverAt(4)).toEqual({ index: 1, played: true });
  });

  it("orients the board to the solver and numbers moves from the FEN", () => {
    expect(solverColor(mate2)).toBe("white");
    expect(moveNumber(mate2, 0)).toBe("18…");
    expect(moveNumber(mate2, 1)).toBe("19.");
    expect(moveNumber(mate2, 2)).toBe("19…");
  });
});

describe("filters", () => {
  const p = (id: string, r: number, s: (0 | 1)[], t: string[] = []): Puzzle => ({ ...mate2, id, r, b: Math.floor((r - 400) / 200), s, t });
  const d = ds([p("a", 500, [1, 1, 1, 1, 1], ["fork"]), p("b", 1500, [0, 1, 0, 0, 1], ["pin"]), p("c", 2500, [0, 0, 0, 1, 1])]);
  const f0 = defaultFilters(d.models.map((m) => m.key));

  it("keeps everything by default, sorted by rating", () => {
    expect(applyFilters(d, f0).map((x) => x.id)).toEqual(["a", "b", "c"]);
    expect(applyFilters(d, { ...f0, sort: "-rating" }).map((x) => x.id)).toEqual(["c", "b", "a"]);
  });

  it("filters by rating, theme, search and per-model outcome", () => {
    expect(applyFilters(d, { ...f0, minR: 1000, maxR: 2000 }).map((x) => x.id)).toEqual(["b"]);
    expect(applyFilters(d, { ...f0, theme: "pin" }).map((x) => x.id)).toEqual(["b"]);
    expect(applyFilters(d, { ...f0, q: "FORK" }).map((x) => x.id)).toEqual(["a"]);
    const want = { ...f0.want, primer_rl: "yes" as const, rl: "no" as const };
    expect(applyFilters(d, { ...f0, want }).map((x) => x.id)).toEqual(["c"]);
  });

  it("computes solve rates overall and per bin", () => {
    expect(solveRates(d, d.puzzles)).toEqual([1 / 3, 2 / 3, 1 / 3, 2 / 3, 1]);
    const { n, rates } = binRates(d);
    expect(n[0]).toBe(1);
    expect(rates[3][10]).toBe(1);
    expect(rates[0][5]).toBe(0);
  });
});

describe("themes", () => {
  it("names themes and lists tactics first", () => {
    expect(themeName("mateIn2")).toBe("Mate in 2");
    expect(themeName("xRayAttack")).toBe("X ray attack");
    expect(tacticsFirst(["short", "middlegame", "fork"])).toEqual(["fork", "middlegame", "short"]);
  });
});
