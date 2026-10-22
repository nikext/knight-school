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
| `rl_train` | 66,008 positions (29,927 puzzles) | from the remaining puzzles, stratified by rating | manifest only |
| `primer_pool` | the rest (3,281,538 puzzles) | puzzle positions available to the primer | manifest only |

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

**Frozen formats** (`ks.data.primer`, ADR-015). Each example is a chat:
the RL system prompt; then a user turn of `Position (FEN): …`,
`Side to move: …` and the question; then the answer. Only T5 also shows the
RL prompt's `Legal moves:` line.

| Task | Question | Answer |
|---|---|---|
| T1 | `What is on e4?` · `List White's pieces.` | `white knight` / `empty` · `Ke1 Qd1 Ra1 Rh1 … a2 b2` (K Q R B N, then pawns as bare squares, each in a1…h8 order) |
| T2 | `How many legal moves does the side to move have? List them.` · `Legal moves of the piece on f3?` | `20: Na3, Nc3, …` · `Nd4, Ne5` or `none` |
| T3 | `FEN after Nxe5?` | full FEN (`board.fen()`) |
| T4 | `Is the side to move in check?` · `Which White pieces attack d5?` · `List all captures.` | `no` / `yes, by Re1 and Bb5` · piece list or `none` · SAN list or `none` |
| T5 | `Best move?` | SAN |
| T6 | `Who is better?` | `Equal (+0.3)` (\|cp\| < 50), `White is slightly better (+1.2)` (< 150), `… is better` (< 300), `… is winning (+3.2)`, `Black mates in 2 (#-2)`; White's view |
| T7 | `Best line, 3 moves?` | `Nf3 Nc6 Bb5` (shorter only if it ends in mate) |

Sources: T1–T5 draw half their positions from primer_pool solver positions
(T5 then answers with the puzzle solution) and half from the eval-DB sample.
T6/T7 use the eval DB only. Each position is used once. Items that show or
reveal a blocklisted or rl_train position are dropped. The examples carry
`keys` so `contamination_hits` can be re-checked.

**Sizes** (tokens counted with the chosen model's tokenizer, in M2):

| Set | Target tokens | Measured (Qwen3.5-2B, M2) | Built in |
|---|---|---|---|
| primer-S | ~15M | **18.6M** total, 2.8M answer (130k examples) | M1 |
| primer-M | ~150M | **186.5M** total, 28.1M answer (1.3M examples) | M1 |
| primer-L | ~450M | | M5 (only if E4 runs) |
| primer-rules-M | T1–T4 only, matched to M's tokens | | M5 (E5a) |

M1 can't know the final tokenizer yet, so it generates by example count with
a ~20% margin. A 3k-example sample measured **139 tokens per example** with
Qwen3's tokenizer (T5 195, T2 151, T3 134, T1 100, T4 94, T6 95, T7 98;
ChatML framing included). That gives **primer-M = 1.3M examples** (~180M
tokens) and **primer-S = its first 130k** (nested). M2 records the exact
token counts per set in the manifests.

**Measured in M2** (`ks primer-tokens qwen3.5-2b`, the non-thinking chat
template, per-task counts in `manifests/primer_{S,M}.json`): **143 tokens
per example**. The sets came out 24% over target because no examples
were trimmed after the margin. Answer tokens are 15% of the total, and
SFT loss is taken on those only, while compute is paid on all of them.
Primer-M stays at 1.3M examples, so E3/E4 compare the sets as built.

## 8. File layout

```
data/
  raw/lichess_db_puzzle.csv.zst (+ .csv)  raw/chessbench/puzzles.csv   # not uploaded
  evaldb/sample.parquet               # 2M eval-DB positions (fen, side-to-move cp/mate, PV)
  puzzles/filtered.parquet            # + game_id, rating_bin, order
  splits/{rl_train_puzzles,primer_pool}.parquet
  positions/rl_train_candidates.parquet
  positions/rl_train.parquet          # expanded + reward tables, after the mismatch filter
  positions/rewards/{in,out-n1000000}/shard-*.parquet   # resumable work dir, not uploaded
  positions/rewards/out-n1000000/secs.json   # engine seconds per shard → cpu_hours
  primer/{S,M}/shard-*.jsonl.zst      # L, rules-M in M5
manifests/*.json                      # committed
evals/sets/{test2000,dev500,probe500,chessbench1k}.csv, test500.ids,
  blocklist.{epd,games}.txt           # committed
```

`make data` (= `ks data`) runs the steps `puzzles evaldb probe blocklist
rltrain timing rewards primer chessbench`. `ks data <step> [--force]` runs
some of them. A step is skipped when its manifest's fingerprint (input
hashes, parameters, module source) matches and its outputs still hash to
what the manifest says. `make upload-data` copies `data/` (minus raw, logs and
reward shards) to `gs://$BUCKET/data/v1/`.

## 9. Data card (M1, built 2026-10-21)

All numbers come from `manifests/*.json`. The data lives in
`gs://knight-school-nt26-knight-school/data/v1/` (everything under `data/` except
`raw/`, `logs/` and the per-shard reward files).

| Item | Value |
|---|---|
| Puzzles downloaded / after each filter | 6,157,341 → NbPlays ≥ 200: 4,024,575 → RatingDeviation ≤ 90: 3,383,515 → Popularity ≥ 50: 3,375,981 → rating 400–2800: 3,375,110 → ≤ 4 solver moves: **3,313,967** (each from a different game) |
| Games in test / dev | 2,000 / 500 (one puzzle per game, disjoint, all in `blocklist.games.txt`) |
| Blocklist | 14,819 position keys (test2000 11,368, dev500 2,826, probe500 625) and 2,500 games |
| rl_train positions / dropped as solution-vs-engine mismatch | 66,008 positions from 29,927 puzzles / **1** dropped (Δwp > 0.15). Before that: 1 blocklist hit and 13 duplicate keys dropped from 66,023 candidates |
| Stockfish version, nodes N, total CPU hours | Stockfish 19 (sf_19, x86-64 build, NNUE `nn-1a298aa575a0`), **N = 1,000,000**, 1 thread and 64 MB hash per position, MultiPV over all legal moves. 3.2 h wall on 18 workers (i7-12700H); **56.5 engine-hours** (`cpu_hours` in `manifests/rl_train.json`, summed from the per-shard seconds in `secs.json`). Timing sample: `manifests/rewards_timing.json` |
| Stockfish-top-move = solution rate | **99.7%** (99.94% counting "both moves mate" as agreement) |
| Primer S / M: examples | S 130,000 (3 shards) / M 1,300,000 (26 shards); S is the first 130k of M |
| Primer per task (S / M examples; est. tokens S / M) | T1 12,987 / 130,502 (1.3M / 13.0M) · T2 19,678 / 195,590 (3.0M / 29.6M) · T3 19,541 / 195,136 (2.6M / 26.2M) · T4 13,141 / 130,107 (1.2M / 12.2M) · T5 38,697 / 389,918 (7.6M / 76.2M) · T6 13,053 / 129,617 (1.2M / 12.2M) · T7 12,903 / 129,130 (1.3M / 12.6M) · **total ~18M / ~182M** |
| Primer sources (M) | eval DB 779,356, puzzle positions 520,644; 235 items dropped for touching the blocklist, 351 for touching rl_train |
| Eval-DB sample | 2,000,000 positions, reservoir over the first 30M lines of `lichess_db_eval.jsonl.zst` (Last-Modified 2026-10-02, 22,423,777,007 bytes); 13.9% mate scores |
| chessbench1k | 1,000 puzzles from the Searchless Chess 10k, 568 excluded for touching training data; mean rating 1458 vs 1461 for the 10k |
| Contamination hits (must be 0) | **0** in every manifest (rl_train_candidates, rl_train, primer_S, primer_M, chessbench1k) |

Token counts are estimates: the per-task mean from a 3k-example sample with
Qwen3's tokenizer (ChatML framing included) times the example count. M2
records exact counts with the chosen model's tokenizer.

**Reproducibility.** `make data` is deterministic given its inputs (seed 2026),
and a second full run on 2026-10-21 reproduced all ten manifests' output hashes. Two inputs are
mutable upstream: Lichess republishes the puzzle and eval databases monthly.
The manifests record each source's sha256 or Last-Modified/size. A rebuild
after a refresh produces different splits, so the GCS copy of `data/v1/` is
the canonical version.
