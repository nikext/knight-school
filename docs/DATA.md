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
  (`e1h1`; seen in the stream on 2026-10-21). `ks.chess.board.pv_to_san`
  parses it with `chess.Board(fen, chess960=True)` and emits SAN. A
  standard `e1g1` in a PV is rejected, not silently misread (unit-tested).
- Take the evaluation with the highest depth and its first PV. `cp` and
  `mate` are from White's point of view (verified 2026-10-21: in Black-to-move
  positions the PVs are sorted by ascending cp), so `ks.data.evaldb` flips
  them to the side to move.
- The file is huge (22.4 GB compressed, 2026-10-02 export). **Stream it** and
  stop early. M1 keeps a 2M-position reservoir sample (Algorithm R, seed
  2026) of the first 30M lines in `data/evaldb/sample.parquet`; the
  manifest records the seed, the lines read and the file's Last-Modified.
  Streaming runs at about 4.5 MB/s, so this takes 20–30 min.

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
is_last, rating, themes`. `legal_san` is sorted the way the prompt shows it. **Frozen in M1:** plain
code-point order of the SAN strings (`ks.chess.board.sort_san`), so piece
moves come first (`B…, K…, N…, O-O, Q…, R…`) and pawn moves last
(`a3, exd5, …`). `fen` is python-chess's `board.fen()`, which writes the ep
square only when an ep capture is legal. `ply` is the solution move's index in
`Moves` (1, 3, 5, 7).

- **Move accuracy** is scored per position.
- **Solve rate** is scored per puzzle. The model must find every solver move,
  with the opponent's replies taken from the solution, and any mate accepted
  on the last move (`ks.chess.board.solver_move_ok`, unit-tested).

## 5. Contamination filter

- **Key:** `board.epd(en_passant="legal")`, i.e. piece placement, side to
  move, castling, and the ep square only if an ep capture is legal (verified
  on python-chess 1.11.2, `ks.chess.board.key`, unit-tested). Move counters
  are not part of the key.
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

- **Stockfish:** **Stockfish 19** (`sf_19`, released 2026-09-05), the same
  major version as chess-lab. From 19 on, the release ships one "universal"
  x86-64 binary that picks AVX2/BMI2/AVX-512 code at runtime, so there is no
  per-CPU build to choose. `stockfish-linux-x86-64-universal.tar.gz`, sha256
  `9defc0d4…e03611f` (matches GitHub's asset digest), installed to
  `~/.local/bin/stockfish` (binary sha256 `0f83d24c…4c12da19`). NNUE
  `nn-1a298aa575a0.nnue`. The version string is in every manifest.
- **Settings per position:** `Threads=1`, `Hash=64`,
  `MultiPV = number of legal moves` (Stockfish 19's MultiPV max is 256,
  verified from the `uci` option list; no position has more than 218 legal
  moves), `go nodes N`, and a `ucinewgame` before every position (python-chess
  `game=object()`), which clears the hash so a table is reproducible. Run 18
  worker processes, leaving 2 threads for the desktop. Shards of 250
  positions are written atomically, so a run resumes where it stopped.
- **Choosing N:** time 200 positions at N ∈ {100k, 300k, 1M}, then pick the
  largest N that finishes 60k positions in ≤ 4 h. Also check how stable the
  top-move ranking is between the N values.
- **Win probability** (Lichess formula), side to move:
  `wp = 0.5 + 0.5 * (2 / (1 + exp(-0.00368208 * cp)) - 1)`, with `cp`
  clamped to ±1000 first, as lila does. Mate for the side to move gives
  `wp = 1`, mate against gives `0`.
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
