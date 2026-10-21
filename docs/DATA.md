# Data

Everything here is built on the laptop (`make data`) and costs nothing except
GCS storage. Raw and built files go to `data/` (gitignored), mirrored to
`gs://$BUCKET/data/<version>/`. Each built artefact gets a manifest in
`manifests/` (committed) with its sha256, row counts, seed, generator git
SHA and Stockfish version.

## 1. Sources

| Source | URL | Size (2026-10-21) | License |
|---|---|---|---|
| Lichess puzzles | `https://database.lichess.org/lichess_db_puzzle.csv.zst` | 6,157,341 puzzles | CC0 |
| Lichess evaluations | `https://database.lichess.org/lichess_db_eval.jsonl.zst` | 416,442,401 positions | CC0 |
| ChessBench puzzles (Ruoss et al.) | `google-deepmind/searchless_chess` repo, `puzzles.csv` | 10k | verify the license |

**Puzzle CSV columns** (verified on the download page 2026-10-21): `PuzzleId,
FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl,
OpeningTags, DailyDate`. Notes:

- `FEN` is the position **before the opponent's move**. `Moves` is a UCI list
  where the **first move is the opponent's**. The solver's moves are the 2nd,
  4th, … entries, with the opponent's replies in between.
- On the **last** move, Lichess accepts any checkmating move, not just the
  listed one. The grader must accept it too.
- `Popularity` runs from −100 to 100. `DailyDate` (Unix ms) is set only for
  daily puzzles.

**Eval JSONL** (verified 2026-10-21):
`{"fen": …, "evals": [{"knodes", "depth", "pvs": [{"cp"|"mate", "line"}]}]}`.

- The FEN has only 4 fields (no move counters). Append ` 0 1` before parsing.
- `line` is in **UCI_Chess960** format, so castling is king-takes-rook
  (`e1h1`). Parse it with `chess.Board(fen, chess960=True)` and emit SAN.
  Unit-test this, because it is an easy bug.
- Take the evaluation with the highest depth and its first PV. `cp` and
  `mate` are from White's point of view (verify), so convert them to the side
  to move.
- The file is huge. **Stream it** (`curl | zstd -dc`) and stop early. Don't
  download all of it. Reservoir-sample over the first ~30M lines and record
  the seed and line count in the manifest, since the file order may be biased.

## 2. Puzzle filtering

Keep puzzles with all of these, then record the counts at each step in the
data card (§9):

- `NbPlays ≥ 200`, `RatingDeviation ≤ 90`, `Popularity ≥ 50`;
- `400 ≤ Rating ≤ 2800`;
- at most 4 solver moves (the expanded positions are what RL trains on).

## 3. Splits

Split **by game** (`GameUrl`), so two puzzles from the same game never
straddle splits. All split files are deterministic given the seed.

| Split | Size | How | Committed? |
|---|---|---|---|
| `test2000` | 2,000 puzzles | stratified: 12 rating bins of 200 Elo (400–2800), about 167 each | yes, full rows (`evals/sets/test2000.csv`) |
| `test500` | 500 ⊂ test2000 | stratified subset, for expensive models (Gemini Pro) | yes, ids |
| `dev500` | 500 puzzles | stratified the same way; for curves during training | yes, full rows |
| `probe500` | 500 items | E0 diagnostic (EVALS.md §4), from held-out eval-DB positions | yes |
| `rl_train` | ~60k positions | from the remaining puzzles, stratified by rating | manifest only |
| `primer_pool` | the rest | puzzle positions available to the primer | manifest only |

`rl_train` and `primer_pool` come from **disjoint puzzle sets**. That keeps
RL's contribution separable from the primer's (RESEARCH.md H5).

## 4. Expansion: puzzle → solver positions

For each puzzle, apply the opponent's first move. That gives the first
solver position, whose target is the solution's 2nd move. Apply the target
and the opponent's reply to get the next position, and so on.

Each record: `puzzle_id, ply, fen, legal_san[], solution_san, solution_uci,
is_last, rating, themes`. `legal_san` is sorted the way the prompt shows it
(alphabetical SAN; decide once, test it, never change it).

- **Move accuracy** is scored per position.
- **Solve rate** is scored per puzzle. The model must find every solver move,
  with the opponent's replies taken from the solution, and any mate accepted
  on the last move.

## 5. Contamination filter

- **Key:** `board.epd(en_passant="legal")`, i.e. piece placement, side to
  move, castling, and the ep square only if an ep capture is legal (verify the
  python-chess API).
- **Blocklist:** every position along every line of `test2000`, `dev500` and
  `probe500` (pre-move, post-opponent-move and later plies). Write it to
  `evals/sets/blocklist.epd.txt`, sorted and committed. The eval puzzles'
  `GameUrl`s go to `evals/sets/blocklist.games.txt`, so no puzzle from those
  games enters `rl_train` or `primer_pool`.
- **Enforcement:** the `rl_train` expansion, the reward tables and every
  primer generator drop blocklisted keys. Their manifests record
  `contamination_hits: 0`. A unit test checks the filter on fixtures, and
  another test asserts that every committed manifest says `0`.

## 6. Stockfish reward tables (for `rl_train`)

- **Stockfish:** the latest official release, a native binary installed to
  `~/.local/bin/stockfish` in M1, with its version recorded in every
  manifest. Chess-lab uses Stockfish 19 (WASM). Use the same major version if
  it is still current.
- **Settings per position:** `Threads=1`, `Hash=64`,
  `MultiPV = number of legal moves` (Stockfish caps MultiPV at 256 and no
  position has more than 218 legal moves; verify the cap), and
  `go nodes N`. Run 18 worker processes, leaving 2 threads for the desktop.
  It must be resumable (write in shards).
- **Choosing N:** time 200 positions at N ∈ {100k, 300k, 1M}, then pick the
  largest N that finishes 60k positions in ≤ 4 h. Also check how stable the
  top-move ranking is between the N values.
- **Win probability** (Lichess formula), side to move:
  `wp = 0.5 + 0.5 * (2 / (1 + exp(-0.00368208 * cp)) - 1)`. Mate for the
  side to move gives `wp = 1`, mate against gives `0`.
- **Store per position:** key, fen, legal_san[], solution_san, wp[] and
  cp_or_mate[] aligned with legal_san, sf_best_san, nodes, sf_version.
- **Data-quality stat:** the share of positions where Stockfish's top move is
  the solution move (or both mate). Report it in the data card. Positions
  where the solution's wp is more than 0.15 below the best move's wp are
  dropped from `rl_train`, and the drop count is reported.

## 7. Primer tasks (teacher-free)

The primer is generated with python-chess and the eval DB. Answers are short
and direct, with no reasoning. The chat template and system prompt are the
same as the RL prompt's, minus the thinking instruction. Positions come from
the eval DB (reservoir sample) and `primer_pool`, after the blocklist filter.

| Task | Prompt (after FEN) | Answer | Weight |
|---|---|---|---|
| T1 board reading | "What is on e4?" / "List White's pieces." | `white knight` / `Ke1 Qd1 Ra1 …` | 10% |
| T2 legal moves | "List all legal moves." / "Legal moves of the piece on f3?" | sorted SAN list | 15% |
| T3 move effect | "Position after Nxe5?" | resulting FEN | 15% |
| T4 attacks and checks | "Is the side to move in check? By what?" / "Which pieces attack d5?" / "List all captures." | short list | 10% |
| T5 best move | "Best move?" | Stockfish best move, SAN | 30% |
| T6 evaluation | "Who is better?" | bucket + score, e.g. `White is winning (+3.2)` | 10% |
| T7 best line | "Best line, 3 moves?" | first 3 plies of the PV, SAN | 10% |

**Sizes** (tokens counted with the chosen model's tokenizer, in M2):

| Set | Target tokens | Built in |
|---|---|---|
| primer-S | ~15M | M1 |
| primer-M | ~150M | M1 |
| primer-L | ~450M | M5 (only if E4 runs) |
| primer-rules-M | T1–T4 only, matched to M's tokens | M5 (E5a) |

M1 can't know the final tokenizer yet, so it generates by example count with
a ~20% margin. M2 records the exact token counts per set in the manifests.

## 8. File layout

```
data/
  raw/lichess_db_puzzle.csv.zst
  puzzles/filtered.parquet  splits/*.parquet
  positions/rl_train.parquet          # expanded + reward tables
  primer/{S,M,L,rules-M}/shard-*.jsonl.zst
manifests/*.json                      # committed
evals/sets/{test2000,dev500,probe500}.csv, test500.ids, blocklist.{epd,games}.txt   # committed
```

## 9. Data card (fill in during M1)

| Item | Value |
|---|---|
| Puzzles downloaded / after each filter | |
| Games in test / dev | |
| rl_train positions / dropped as solution-vs-engine mismatch | |
| Stockfish version, nodes N, total CPU hours | |
| Stockfish-top-move = solution rate | |
| Primer S / M: examples, tokens per task | |
| Contamination hits (must be 0) | |
