# Build plan

Work top to bottom, **one milestone per fresh Claude Code session**. Each
milestone has a self-contained task file in `docs/tasks/`. Each one ends in a
merged PR whose description lists what was verified, the numbers, and the
`make costs` output. Update this table in the same PR.

## Status

| # | Milestone | Task file | compute $ | vertex $ | Status | PR / notes |
|---|---|---|---|---|---|---|
| M0 | Bootstrap and money guardrails | [M0](tasks/M0-bootstrap.md) | 5 | 1 | ✅ done | PR #1 · spent $0.08 compute, $0.000001 vertex · L4 smoke passed (r2); kill switch tested |
| M1 | Data: puzzles, splits, Stockfish rewards, primer | [M1](tasks/M1-data.md) | 1 | 0 | ✅ done | PR #2 · spent $0.02 compute (GCS storage) · 66,008 rl_train positions, SF19 N=1M, 99.7% agree · primer S 130k / M 1.3M · 0 contamination |
| M2 | Eval harness, container, model choice, baselines (E0, E1) | [M2](tasks/M2-evals-baselines.md) | 15 | 50 | ✅ done | PR #3 · spent $4.85 compute, $0 vertex · main model Qwen3.5-2B, non-thinking (ADR-011, ADR-017) · E1 base 4.1% solve, 96.4% legal · Stockfish 1 node 68.6% · Gemini rows pending until 2026-11-13 |
| M3 | GRPO pipeline, RL on base (E2), re-plan | [M3](tasks/M3-grpo.md) | 70 | 0 | ✅ done | PR #4 · spent $50.15 compute, $0 vertex · config v2 frozen (ADR-021, adaptive entropy) · E2 test2000: dense v2 27.2%, sparse v2 23.5%, dense v1 23.8% (base 4.1%) · post-answer rambling flaw found, v3 proposed |
| M4 | Primer SFT → GRPO, the main result (E3) | [M4](tasks/M4-primer.md) | 100 | 0 | ✅ done | PR #5 · spent $75.92 compute, $0 vertex · config v3 (ADR-022), T8 fallback (ADR-024) · test2000: primer-M+T8 only 35.7%, primer → dense 32.6%, primer → sparse 35.4%, E2 v3 dense 25.8% / sparse 28.0% · H1 holds, H2 falsified, H5 fails (ADR-026, entropy ablation ADR-025) |
| M5 | Scaling and ablations (E4, E5) | [M5](tasks/M5-scaling-ablations.md) | 110 | 110* | 🟨 in progress | branch `m5-scaling-ablations` · plan: E5a, E4, E5b, E5d (E5c ⏭️) · config v4 (ADR-027) · rules-M needed T9 at 10% (ADR-028–030) |

**Next up (M5, 2026-10-25):** the user approved one queue of every remaining M5 run:
`m5-sft-rules-m-t9-10` → `m5-e5a-dense` → `m5-sft-primer-s-t8` → `m5-e4-dense` →
`m5-e5b-dense-nolist` → `m5-e5d-r8` → `m5-e5d-r64`. All predictions are committed in RESULTS.md.
Then: evaluate each arm with paired CIs (`ks compare`), the E4 figure, the H3/H4 verdicts, the cost
summary, and the PR.
| M6 | Release and showcase | [M6](tasks/M6-release.md) | 9 | 4 | ⬜ todo | |
| | contingency (user approval only) | | 50 | 15 | | |
| | **ceiling** | | **360** | **180** | | |

Legend: ⬜ todo · 🟨 in progress · ✅ done · ⏭️ skipped (say why)

## Calendar (ADR-013)

The compute credit expires **2026-11-12**. The gate refuses any job that
could still run after **2026-11-10 00:00Z**. Gemini may only spend from
2026-11-13, on the second credit. Target dates, with sessions every 2–3 days:

| Milestone | Target | Hard limit |
|---|---|---|
| M1 data (laptop) | Oct 22–23 | — |
| M2 harness, container, model choice, open-model baselines | Oct 24–26 | Gemini rows wait for Nov 13 |
| M3 GRPO + E2 + re-plan | Oct 27–31 | |
| M4 primer → GRPO (E3) | Nov 1–5 | |
| M5 scaling / ablations, whatever fits | Nov 5–9 | GPU jobs end by Nov 10 00:00Z |
| M6a final evals, downloads, empty bucket and registry | Nov 9–11 | storage gone by Nov 11 |
| E1-Gemini (scope test → pilot → batch) | from Nov 13 | vertex pool only |
| M6b HF release, site, blog, CV | after | no compute spend |

\* Only if the Vertex credit covers Vertex AI custom training (checked in M0).

Spent to date: compute $55.10 · vertex $0.00 (as of M3, 2026-10-23; update from `make costs` in each PR).

---

## Milestone summaries

Details, tasks and "Done when" live in the task files. These summaries are
for orientation only.

**M0: Bootstrap and money guardrails.** Tooling (uv, ruff, pyright, pytest,
CI). The user picks the GCP project and reads the remaining credits.
`infra/setup.sh` creates the bucket, registry and service accounts. GPU quota
is requested at 1. Real prices are fetched into `costs/prices.yaml`. Then the
`ks.cloud` gate (ledger, launcher, sweep, reconcile) is built with unit tests,
followed by the budgets and the tested kill switch. It ends with a 15-minute
L4 spot smoke VM that deletes itself and closes cleanly in the ledger.
**No experiment code yet.**

**M1: Data (laptop only).** Pinned Stockfish. Lichess puzzle DB → filtered →
test2000 / dev500 / train splits, split by game. Puzzles are
expanded into solver positions. Stockfish MultiPV reward tables are built for
the training positions on the laptop's 18 threads. The primer generators
(T1–T7) are built and the S and M primer sets generated. The contamination
filter and data card are committed. Datasets are uploaded to GCS.

**M2: Eval harness, container, model choice, baselines.** Prompt builder,
answer parser, rewards, metrics with bootstrap CIs, puzzle-rating fit, and the
E0 diagnostic probe. The pinned vLLM + TRL container is built and pushed.
Candidate ~2B models are screened on dev500 (on the laptop where they fit,
otherwise on a spot L4), plus a 5-step GRPO compatibility smoke on an L4.
The main model is chosen (ADR). Then E1 baselines: random, weak Stockfish,
the open candidates, and Gemini (pilot → ask → batch).

**M3: GRPO pipeline and RL on the base model.** The `ks.train.grpo` entry
point (TRL GRPOTrainer, vLLM colocate, LoRA), GCS checkpoints with resume,
and a preemption test. Smoke on an L4. A throughput measurement picks A100
vs H100 by $/step, and the GRPO config is frozen. E2: sparse vs dense reward
on the base model, evaluated on test2000. A **re-plan checkpoint** then
prices every remaining run with the measured $/step, and the user approves
it.

**M4: Primer SFT → GRPO (E3, the main result).** `ks.train.sft` (full
fine-tune, completion-only loss) on primer-M. The primer-only control is
evaluated, then GRPO sparse and dense from the primer checkpoint with
configs identical to E2. Learning curves are overlaid and the hypothesis
verdict goes in an ADR.

**M5: Scaling and ablations.** In priority order, until the line runs out:
primer-S → RL (E4 scaling curve: none, S, M), rules-only primer (E5a), no
legal-move list (E5b), LoRA rank (E5d), and a ~4B model with the best recipe
(E5c, conditional). Skipped items get a reason. **Re-plan (M3, user-approved
2026-10-22, BUDGET.md §2):** primer-L is dropped, because it needs new data and the
most expensive SFT. E5c is decided at the start of M5 from the measured SFT cost
and any reallocated M3/M4 underrun.

**M6: Release and showcase.** Hugging Face models and datasets with cards,
a static "puzzle browser" site showing reasoning before and after RL, README
results, a blog draft, CV bullets, and an optional portfolio entry. Final
teardown and a cost reconciliation ("spent $X of $600").

## Stretch backlog (only after M6, budget permitting)

- Local play in `chess-lab`: a GGUF build of the final model as a third
  "player" next to Stockfish and Jev (ask before touching that repo).
- Full games vs Stockfish at fixed skill levels → an Elo estimate, offline
  only and never on Lichess against humans.
- verl instead of TRL, if M3 showed TRL's throughput was the bottleneck.
- Curriculum by puzzle rating vs uniform sampling.
