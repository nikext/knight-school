/** [shown answer, uci if legal, correct] */
export type Answer = [string, string | null, 0 | 1];

export interface Puzzle {
  id: string;
  /** Lichess rating */
  r: number;
  /** rating bin index */
  b: number;
  /** Lichess themes */
  t: string[];
  /** FEN before the opponent's set-up move */
  fen: string;
  /** every move in UCI, the set-up move first */
  m: string[];
  /** solved per model, in `Dataset.models` order */
  s: (0 | 1)[];
  /** a[i][j]: model j's answer at solver position i */
  a: Answer[][];
}

export interface CI {
  value: number;
  lo: number;
  hi: number;
}

export interface ModelInfo {
  key: string;
  label: string;
  blurb: string;
  run: string;
  solve: CI;
  move_acc: number;
  legal: number;
}

export interface Dataset {
  set: string;
  bins: string[];
  models: ModelInfo[];
  puzzles: Puzzle[];
}

export type Want = "any" | "yes" | "no";

export interface Filters {
  q: string;
  minR: number;
  maxR: number;
  theme: string;
  want: Record<string, Want>;
  sort: "rating" | "-rating" | "id";
}
