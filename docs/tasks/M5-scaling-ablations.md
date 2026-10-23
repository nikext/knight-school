# M5: Scaling and ablations (E4, E5)

**Goal:** turn the one-point E3 result into a curve and an explanation.
Run the arms below **in priority order** until the M5 line runs out.
Skipped arms are recorded with the reason. Nothing here is mandatory except
honesty about what ran.

**Budget:** compute $110, plus vertex $110 **only if** M0 confirmed the
Vertex credit covers custom training (then use the `vertex` backend for some
arms, so they draw on the vertex pool). Contingency is only spent with the
user's explicit approval.

**Read first:** RESEARCH.md §3–4, the E3 section of RESULTS.md, the M4 ADR
on priorities, and DATA.md §7 (for primer-L and rules-M).

## Priority list

Each arm runs the SFT primer and then GRPO dense, with the frozen config and
the same positions and seed, then gets a test2000 eval and E0.

| # | Arm | Why | Estimate |
|---|---|---|---|
| 1 | **E4** primer-S → GRPO dense | the second point on the scaling curve (cheap) | ~$15 (BUDGET.md §2 re-plan) |
| 2 | **E5a** rules-only primer (T1–T4, tokens matched to M) → GRPO dense | rules vs moves (H4), the most interesting "why" | ~$33–43 |
| 3 | ~~**E4** primer-L → GRPO dense~~ | **dropped in the M3 re-plan** (new data + the most expensive SFT, ~$105) | — |
| 4 | **E5b** best primer recipe, prompt without the legal-move list | does the primer replace the crutch? | ~$12 |
| 5 | **E5c** ~4B sibling, best recipe (primer → GRPO dense) | does it hold at a larger size? | ~$85; **conditional**: decide at M5 start with the measured SFT cost (needs M3/M4 underrun moved to M5, user's call) |
| 6 | **E5d** LoRA r=8 vs r=64 on dev only, short runs | a cheap check of ADR-007 | ~$12 |

The M4 ADR may reorder these. If it does, follow it.

## Tasks

1. Generate primer-L and primer-rules-M on the laptop (DATA.md §7). Count
   their tokens, write the manifests (0 contamination hits), and upload.
   Besides the blocklist, these sets must also drop every position on a
   `chessbench1k` line (M1 left it out of the blocklist; see EVALS.md §1).
   primer-L needs ~3× M's positions, so stream a larger eval-DB sample
   (`EVALDB_K`), or allow reuse and say so in an ADR.
2. Before starting, show the user the priority table with current cost
   estimates and the remaining line. Agree on which arms to attempt.
3. For each arm, in order:
   - commit the prediction;
   - ask and launch;
   - evaluate;
   - update RESULTS.md;
   - re-check the remaining budget before the next arm.
4. **E4 figure:** post-RL solve rate vs primer tokens (log x), with CIs.
   Include "no primer" (E2) as the x=0 point, drawn separately.
5. **Verdicts** for H3 and H4. Write the final RESULTS.md cost summary rows
   for M5.

## Done when

- Every attempted arm is evaluated with CIs, and every unattempted arm is
  marked ⏭️ with its reason.
- The E4 figure is committed and the H3 and H4 verdicts are written.
- Spend is within the line (plus any approved contingency), the ledger is
  reconciled, `make sweep` is clean, the PLAN.md row is updated, and the PR
  has the `make costs` output.
