# M3: GRPO pipeline and RL on the base model (E2)

**Goal:** a GRPO training job that runs on one spot GPU, survives
preemption, and reports $ per step. Use it for E2 (base → GRPO, sparse vs
dense). Then re-plan M4 and M5 with the measured costs.

**Budget:** compute $70 · vertex $0. Expected: smoke and throughput tests
≈ $5, two E2 runs ≈ $15–25 each, evals ≈ $3.

**Read first:** TRAINING.md (all of it), RESEARCH.md §2–4, BUDGET.md §2–3,
ADR-004, ADR-005 and ADR-007, and the M2 notes in PLAN.md.

## Tasks

1. **Prior-work refresh** (RESEARCH.md §2 asks for it). Search for LLM
   chess or RLVR results from 2026-10 on. Add anything relevant, and say in
   the PR whether it changes the plan.
2. **`ks.train.grpo`:**
   - TRL `GRPOTrainer` with vLLM colocate, LoRA (ADR-007), and rewards from
     `ks.chess.rewards`, with each component logged separately;
   - the dataset from the `rl_train` parquet;
   - a dev500 eval callback every 25 steps;
   - GCS checkpointing and resume, and a SIGTERM handler (TRAINING.md §7);
   - `run.json`, and per-step metrics including $/step.

   Pin the library versions in the image and rebuild it.
3. **Local wiring test** on the laptop GPU with a ≤ 1B model, 2–3 steps.
   Use `use_vllm=False` if colocate won't fit in 6 GB. It must pass before any
   cloud run. Kill it halfway and resume, to test resume.
4. **L4 smoke** with the main model: 20 steps, LoRA. Ask first; ≈ $0.50.
   Check the reward components move, the format reward is learnable, and no
   OOM occurs. Read the completion lengths, then set `max_completion_length`
   (TRAINING.md §4).
5. **Throughput:** 10 steps on `a2-ultragpu-1g` and 10 on `a3-highgpu-1g`,
   same config. Ask first; ≈ $1–2. Pick the machine by **$ per step** and
   record it in an ADR. Tune `vllm_gpu_memory_utilization` and the
   batch/accumulation split here, then **freeze the GRPO config** for every
   later arm (ADR). Changing it later would invalidate the comparisons.
6. **Re-plan checkpoint.** From the measured $/step, compute the expected
   cost of every remaining planned run: E2 ×2, M4's SFT + 2 GRPO, and each
   M5 arm. Present the table to the user. If it doesn't fit, propose cuts
   (fewer steps for *all* arms, or dropping low-priority M5 arms), get
   approval, and update PLAN.md, BUDGET.md and caps.yaml if allocations move.
7. **Predictions.** Commit the predicted E2 numbers to RESULTS.md.
8. **E2 runs:** base → GRPO sparse, and base → GRPO dense. One launch each,
   each asked for with its `run_budget_usd`. Watch with Monitor. Evaluate the
   final checkpoint on test2000, and run E0 on the dense checkpoint.
9. **Figures:** dev solve rate vs $ for both arms, plus reward component
   curves. Save to `results/figures/`. Put the numbers in RESULTS.md, with a
   short reading of whether sparse learned and how the plateau compares with
   Chess-R1.

## Done when

- The pipeline is tested locally and in the cloud, preemption/resume is shown
  to work (a real or simulated preemption), and the config is frozen with an
  ADR.
- Both E2 arms are evaluated on test2000 with CIs, and the figures are
  committed.
- The re-plan table is approved by the user and recorded.
- Spend is ≤ $70, the ledger is reconciled, `make sweep` is clean, the
  PLAN.md row is updated, and the PR has the `make costs` output.
