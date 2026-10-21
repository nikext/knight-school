# Evals

## 1. Sets (built in M1, committed under `evals/sets/`)

| Set | Size | Use |
|---|---|---|
| `test2000` | 2,000 puzzles, 12 rating bins | **headline numbers only**; evaluated once per finished checkpoint |
| `test500` | 500 ⊂ test2000 | expensive models (Gemini Pro) |
| `dev500` | 500 puzzles | curves during training, prompt and model screening |
| `probe500` | 500 items | E0 diagnostics (§4) |
| `chessbench1k` (optional) | 1,000 of Ruoss et al.'s 10k puzzles, built in M1 | comparability with Chess-R1; report the metric difference honestly. Same conventions as Lichess puzzles, but no filters (up to 13 solver moves). ChessBench's own grader accepts a mate on any move; ours only on the last, which agrees in practice. Excludes puzzles touching v1 training data; it is **not** in the blocklist, so M5's new training sets must exclude its keys too. CC-BY 4.0: credit Ruoss et al. |

**Never tune anything on `test2000`.** Screening, hyperparameters and
checkpoint selection use `dev500`. The final checkpoint of each run (not the
best dev step) is what gets the test eval, unless an ADR says otherwise
before the run starts.

## 2. Metrics

| Metric | Definition |
|---|---|
| **solve rate** (headline) | share of puzzles where every solver move is right (any mate accepted on the last move); opponent replies from the solution |
| move accuracy | share of solver positions where the move is right (Chess-R1 style) |
| legal rate | share of answers that parse to a legal move |
| format rate | share with exactly one well-formed answer block |
| puzzle rating | rating R at which a logistic fit of P(solve) vs puzzle rating crosses 50%; with a bootstrap CI |
| per-bin solve rate | solve rate in each of the 12 rating bins (chart) |
| pass@k (dev only) | k ∈ {1, 4, 8} at T = 1.0, for the RL analysis (Shen et al.) |
| mean / p95 response tokens | cost and behaviour |
| $ per 1k puzzles | from the cost meter |

**Confidence intervals:** a 95% percentile bootstrap over puzzles (10k
resamples). **Arm-vs-arm:** a paired bootstrap on the same puzzles, reporting
the difference and its CI. Put both in every results table.

## 3. Harness (`ks.eval`)

- `make eval MODEL=<profile> SET=dev500|test2000|… [CKPT=gs://…]` writes
  `results/eval/<set>/<run>.json` (per-item outputs, parsed moves and
  scores) and a `.md` summary. Commit both. For Gemini, gzip the per-item
  file if it's over 5 MB.
- **Backends:**
  - `vllm`: open models and our checkpoints, offline batch generation. Runs
    locally for ≤ 2B models on the 6 GB GPU if it fits (quantize for
    screening only, never for headline numbers), otherwise inside a
    `ks launch` eval job on a spot L4.
  - `gemini`: Vertex AI through the `google-genai` SDK. A 20-item pilot
    first, then batch prediction for full sets (BUDGET.md §6).
  - `stockfish` (baseline): python-chess engine at a fixed node count.
  - `random`: a uniform random legal move with a fixed seed.
- **Decoding:** greedy (T = 0) for pass@1 headline numbers. Max tokens equal
  the training max completion length. Gemini uses its default sampling with
  the thinking setting recorded (greedy isn't meaningful for every Gemini
  model; say so in the report).
- **Model profiles** live in `configs/models/*.yaml` (HF repo or Vertex
  model id, chat template quirks, thinking mode, max tokens). **No model ID
  literals in code.**
- **Cost meter:** every backend reports cost (GPU seconds × price, or tokens
  × price) and the harness stops at the `--max-usd` cap, checked between
  chunks of 512 prompts; a puzzle cut off mid-way is dropped, not graded on
  part of its moves. Ledger: a cloud eval is booked by its `ks launch`
  `start`/`end` events (the VM sets `KS_PRICE_PER_HOUR`, so the report shows
  its share); a Gemini run appends one `charge` (`ks.eval.gemini`); laptop
  runs cost $0 and append nothing.
- **Gemini meter** (`ks.eval.gemini`): refuses before the vertex pool's
  `usable_from`, with a stale credit reading, or while `prices.yaml → gemini`
  is `verified: false`. A run's allowance is the smallest of `--max-usd`, the
  milestone's vertex allocation left, the pool ceiling left and the credit
  headroom. Each call first reserves its worst case (prompt + max output +
  thinking budget at the output price) and then books `usage_metadata`.
  Batch JSONL is built and parsed by `batch_requests` / `parse_batch_output`.
- **Files:** `<run>.json` holds the header (profile, git SHA, prompt hash,
  cost), the summary and every item with its completion text; it is gzipped
  as `<run>.json.gz` when over 5 MB, for any backend.

## 4. E0 probe (`probe500`)

These are diagnostics of chess *knowledge*, not puzzle skill. They are graded
by exact match after normalisation. There are 125 items per task, from
held-out eval-DB positions:

| Task | Question | Graded |
|---|---|---|
| P1 | "What is on <square>?" | exact |
| P2 | "How many legal moves does the side to move have?" + "list them" | count exact; list F1 |
| P3 | "FEN after <move>?" | exact piece-placement field (Chess-R1's board-state test, where every model scored 0%) |
| P4 | "Is the side to move in check?" | exact |

Built in M1 (`evals/sets/probe500.csv`: `id, task, fen, question, answer,
move`). **Prompt (M2):** the primer's user turn (FEN, side to move, the
question, no legal-move list) plus one fixed format line per task, the same
for every model, because a zero-shot model has never seen the primer's answer
formats (`ks.eval.probe.FORMAT_HINT`). The grader reads the last `<answer>`
block if there is one, else the text after `</think>`, else the whole reply. The items come from the primer's own generators (P1 = T1 square,
P2 = T2 all, P3 = T3, P4 = T4 check), so the reference answers use the
primer's frozen formats (DATA.md §7). P4 is balanced, with 63 positions in
check and 62 not. For P4 the grader compares yes/no (the answer's first word).
For P2 it compares the count and the list's F1. For P3 it compares the
FEN's first field.

Run E0 for every base model, every primer checkpoint and every final RL
checkpoint. It shows whether the primer actually installed rules knowledge
and whether RL kept it.

## 5. Baselines (E1)

| Baseline | Sets |
|---|---|
| random legal move | test2000 |
| Stockfish at 1 node and at 1k nodes | test2000 (calibration: what "weak engine" looks like) |
| each candidate base model, zero-shot | dev500 (screening), then test2000 for the chosen one |
| Gemini Flash-Lite and Flash (current ids, verify) | test2000, batch |
| Gemini Pro (current id) | test500, batch |
| Chess-R1 reported numbers | cited, not rerun; note the metric and set differences |

## 6. Report format (`results/eval/<set>/<run>.md`)

A header with the model, checkpoint, git SHA, prompt hash, decoding and
cost. Then a table of solve rate, move accuracy, legal rate, format rate and
puzzle rating, each with its CI, followed by the per-bin table and five
example items (correct, wrong-but-legal, illegal).
