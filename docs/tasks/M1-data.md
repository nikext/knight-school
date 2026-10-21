# M1: Data (laptop only)

**Goal:** `make data` reproducibly builds the filtered puzzles, the
splits, the committed eval sets and blocklist, the `rl_train` positions with
Stockfish reward tables, and the primer-S and primer-M sets, all with
manifests and a filled-in data card. Then everything is uploaded to GCS.

**Budget:** compute $1 (GCS storage only) · vertex $0. **No VMs.** All
compute runs on the laptop (ADR-010).

**Read first:** `docs/DATA.md` (all of it), RESEARCH.md §4 (to see what
the data is for), ADR-005 and ADR-010.

## Tasks

1. **Stockfish.** Check the CPU flags (`grep -o 'avx2\|bmi2\|avx512[a-z]*'
   /proc/cpuinfo | sort -u`). Download the matching official build of the
   latest release (github.com/official-stockfish/Stockfish/releases) to
   `~/.local/bin/stockfish`. Verify its sha256 if published, and record the
   version. No sudo needed.
2. **Download** the puzzle DB to `data/raw/`. The eval DB is streamed, never
   stored whole (DATA.md §1).
3. **`ks.data.puzzles`:** filter (§2), split by game (§3), expand into
   positions (§4), and write `evals/sets/test2000.csv`, `dev500.csv`,
   `test500.ids` and `blocklist.{epd,games}.txt`. The legal-move ordering and the
   SAN conventions are decided here, documented in DATA.md, and frozen.
4. **`ks.data.blocklist`:** the contamination filter (§5), plus the CI test
   that every committed manifest has `contamination_hits: 0`.
5. **`ks.data.rewards`:** Stockfish MultiPV reward tables (§6).
   - First time 200 positions at three node counts and pick N (write the
     timing table into DATA.md).
   - Then run the full ~60k with 18 worker processes, sharded and
     resumable. Run it with `run_in_background` and check progress with
     Monitor; it should take ≤ 4 h. Leave 2 threads free.
   - Compute the solution-vs-engine agreement and apply the mismatch filter.
6. **`ks.data.primer`:** generators T1–T7 (§7) and the probe500 builder
   (EVALS.md §4). Build them on python-chess, stream positions from the eval DB
   (reservoir sample, seeded), parse PVs as UCI_Chess960, and apply the
   blocklist. Generate **primer-S and primer-M** by example count with a
   20% margin, in zstd JSONL shards. Leave L and rules-M for M5.
7. **Manifests** in `manifests/` for every artefact, and `make data` running
   the whole chain (skipping steps whose outputs and inputs are unchanged).
8. **Tests** (CPU, fast, in CI): puzzle expansion (the opponent's first
   move), alternative mate accepted on the last move, SAN↔UCI, the Chess960
   castling conversion, the win-probability formula and mate handling, each
   primer generator's answers against python-chess on fixtures, blocklist hits
   on a fixture containing a test position, and deterministic splits for a
   given seed.
9. **Data card:** fill in DATA.md §9.
10. **Upload** `data/` (minus `raw/`) to `gs://$BUCKET/data/v1/`. Ask once,
    since storage is cents. Log a ledger `charge` with the estimated monthly
    storage cost.
11. **Optional:** fetch ChessBench `puzzles.csv`, check its license, and if it's
    fine, build `chessbench1k`, blocklist-filtered against our train data.

## Done when

- `make data` runs end to end from a clean `data/`, and `make test` is green
  in CI.
- The eval sets and blocklist are committed, every manifest shows 0
  contamination hits, and the data card is filled in.
- Reward tables exist for ≥ 50k `rl_train` positions, and the agreement rate is
  reported.
- primer-S and primer-M exist, with per-task example counts in their
  manifests.
- The data is in GCS, the PLAN.md row is updated, and the PR has the
  `make costs` output (≈ $0).
