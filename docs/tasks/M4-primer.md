# M4: Primer SFT → GRPO (E3, the main result)

**Goal:** answer RQ1, plus H2 and H5. Fine-tune the main model on primer-M,
measure the primer-only control, then run GRPO sparse and dense from the
primer checkpoint with the **frozen** E2 config. Compare against E2.

**Budget:** compute $100 · vertex $0, or whatever the M3 re-plan approved.

**Read first:** TRAINING.md §5 and §7, RESEARCH.md §3–5, the E2 section of
RESULTS.md, and the M3 ADRs (machine choice, frozen config).

## Tasks

1. **`ks.train.sft`** (TRAINING.md §5): TRL SFTTrainer, full fine-tune,
   loss on the answers only, packing, wall-clock checkpointing to GCS with
   resume, and a merged final checkpoint. Run a local wiring test with a
   ≤ 1B model on a slice of primer-S (it must pass, including resume).
2. **Predictions:** commit the E3 predictions (and the E0 primer row) to
   RESULTS.md.
3. **Primer-M SFT run.** Ask with the estimate from M3's $/token figures,
   then launch.
4. **Evaluate primer-only:** test2000, plus E0 on probe500.
   - If the **format rate on dev500 is below 50%**, apply the T8 fallback
     (TRAINING.md §5): generate the T8 examples, rerun SFT (ask; it's
     another SFT cost) and record an ADR.
   - If E0 shows the primer didn't install rules knowledge (P3 board-state
     accuracy still near 0), stop and discuss with the user before spending
     on GRPO. Something is wrong with the primer.
5. **GRPO from the primer checkpoint, sparse and dense.** Use the frozen
   config, the same `rl_train` positions and the same seed as E2. Ask for
   each run. Evaluate the final checkpoints on test2000 and run E0 on the
   dense one.
6. **Second seed** of primer → GRPO dense, **only if** the remaining M4 line
   covers it after step 5 (RESEARCH.md §4). Otherwise note it as skipped.
7. **Analysis:**
   - paired-bootstrap deltas vs E2-dense;
   - curves of all four RL arms on one dev-solve-vs-$ plot;
   - per-bin solve rates (does the primer help easy puzzles, hard ones, or
     both?);
   - pass@k on dev for base, primer, and primer → GRPO (Shen et al.'s
     sharpening vs tail-discovery question).
8. **Verdicts** for H1, H2 and H5 in RESULTS.md, plus an ADR summarising the
   main result and whether it changes the M5 priorities. Draft the
   README's headline sentence (it is finalised in M6).

## Done when

- Primer-only and both primer → GRPO arms are evaluated on test2000 and
  probe500, with CIs and paired deltas against E2.
- The figures are committed, the H1, H2 and H5 verdicts are written, and the
  ADR is added.
- Spend is within the line, the ledger is reconciled, `make sweep` is clean,
  the PLAN.md row is updated, and the PR has the `make costs` output.
