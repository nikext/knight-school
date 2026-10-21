# Decision log (ADRs)

Short ADRs. Add new ones at the bottom with the next free number. When a
decision is revisited, mark the old one **Superseded by ADR-0xx**. Never
delete one.

---

### ADR-001: The project is GRPO on chess puzzles, framed as "does a primer raise the ceiling?"
**Status:** accepted (2026-10-21)
**Context:** The user wants a compute-heavy CV project that fits $400 GCP +
$200 Vertex credits. Their portfolio already has an agent/RAG flagship
(swiss-admin-navigator); what's missing is "trained a model". Chess-R1 showed
small LLMs plateau at ~25–30% under RLVR and blamed missing chess knowledge,
which leaves an open, cheap, testable follow-up.
**Decision:** Train a ~2B open model with GRPO on Lichess puzzles. The
research question is whether a teacher-free SFT primer raises the RL ceiling
(RESEARCH.md).
**Consequences:** The result is publishable either way. Scope stays small
enough for single-GPU spot runs. Prior work gives us hyperparameters and a
point of comparison.

### ADR-002: Spot only, one GPU, quota 1
**Status:** accepted (2026-10-21)
**Context:** GCP has no hard spending cap; budgets only alert, and billing
data lags by hours. A single forgotten 8×H100 node costs about $90/h
on demand.
**Decision:** Spot provisioning only, machines with exactly 1 GPU, and GPU
quota requested at 1. The launcher refuses anything else.
**Consequences:** The worst-case burn rate is about $3/h, enforced by Google
rather than by our code. Some runs take longer and get preempted, so
checkpoint/resume is mandatory (TRAINING.md §7).

### ADR-003: The ledger plus a pre-flight gate is the primary money control; budgets plus the kill switch are the backstop
**Status:** accepted (2026-10-21)
**Context:** Budget notifications lag. Our own accounting is immediate and
worst-case bounded because every job has a hard time limit.
**Decision:** An append-only `costs/ledger.jsonl`. `ks launch` refuses jobs
whose worst case would break a pool ceiling or milestone allocation, and
needs `--confirm` after user approval. There are three budgets (gross total,
gross Vertex, net) → Pub/Sub → a kill-switch function. Details in BUDGET.md.
**Consequences:** Spend is visible in the repo, and the final "spent $X of
$600" line is auditable. The ceilings leave a 10% reserve for lag and small
services.

### ADR-004: TRL GRPOTrainer with vLLM colocate, not verl
**Status:** accepted (2026-10-21); revisit after M3's throughput measurement
**Context:** Chess-R1 used verl on 4×A100. We run single-GPU jobs. TRL
(1.16.0, 2026-10-15) supports GRPO with vLLM colocated on one GPU, and it's
simpler to install, debug and explain.
**Decision:** TRL for both GRPO and SFT. Pin TRL, vLLM and torch together.
**Consequences:** Less peak throughput than verl. If M3 shows generation
dominates step time and TRL is clearly the bottleneck, consider verl in a
new ADR.

### ADR-005: Dense reward from precomputed Stockfish MultiPV, not the 270M critic
**Status:** accepted (2026-10-21)
**Context:** Chess-R1's dense reward came from DeepMind's 270M action-value
net, which needs JAX in the training loop. Stockfish is stronger and
deterministic at a fixed node count. Our RL training set is a fixed 60k
positions, so every legal move's value can be computed in advance.
**Decision:** Precompute Stockfish evaluations for every legal move of every
`rl_train` position on the laptop (M1). Reward is the Lichess win
probability of the chosen move.
**Consequences:** No engine and no JAX in the GPU loop, and no GPL binary in
the image. The reward is a table lookup. RL is limited to the precomputed
positions, which is fine.

### ADR-006: Prompt = FEN + sorted SAN legal-move list; answer = one SAN move
**Status:** accepted (2026-10-21)
**Context:** Chess-R1's ablations: without the legal-move list learning
stops, UCI is worse than SAN, and FEN vs PGN doesn't matter.
**Decision:** Use their winning format (TRAINING.md §2), fixed for every arm.
E5b tests dropping the list after the primer.
**Consequences:** Comparable to Chess-R1. The prompt is longer, because the
legal list costs tokens on every rollout.

### ADR-007: LoRA for GRPO, full fine-tune for the primer
**Status:** accepted (2026-10-21); E5d may check it
**Context:** "LoRA Without Regret" (Thinking Machines, 2025): LoRA matches
full FT for RL even at low rank, but underperforms on large SFT datasets. RL
moves few bits of information; the primer is meant to move many.
**Decision:** GRPO uses LoRA r=32 on all linear layers, lr ≈ 10× the full-FT
value. Primer SFT is a full fine-tune.
**Consequences:** RL checkpoints are tiny and fast to save (good for spot).
The SFT checkpoints are full-size.

### ADR-008: Teacher-free data, with Gemini only as a baseline
**Status:** accepted (2026-10-21)
**Context:** Chess-R1 found that SFT on o3 reasoning traces didn't help.
Using a commercial model's outputs to train another model also raises
terms-of-service questions. The research question is specifically about
knowledge that can be generated without an LLM.
**Decision:** All training data comes from python-chess and Stockfish. Gemini
is evaluated as a baseline only.
**Consequences:** A clean story ("no LLM wrote any training data"). The $200
Vertex credit goes to baselines, plus custom training if the credit allows.

### ADR-009: us-central1 for GPUs, bucket and registry; europe-west4 as fallback
**Status:** accepted (2026-10-21)
**Context:** us-central1 has the widest spot GPU availability and the lowest
prices. Data is CC0 and public, so residency doesn't matter. europe-west6
has few GPU types.
**Decision:** Put the compute, bucket and registry in us-central1. Fall back
to europe-west4 only on stockouts, with inputs mirrored.
**Consequences:** Laptop ↔ bucket transfers cross the Atlantic, which only
affects latency (ingress is free, and downloading results is small).

### ADR-010: Laptop for data and dev, cloud for GPU runs only
**Status:** accepted (2026-10-21)
**Context:** The laptop has 20 threads, 15 GB RAM and an RTX 3060 (6 GB).
Stockfish precompute is CPU-bound and embarrassingly parallel.
**Decision:** M1 runs entirely on the laptop. All code is debugged locally
with tiny models before a cloud run. Cloud GPUs only run code that passed a
local smoke test.
**Consequences:** Saves an estimated $20–40 of CPU VMs and many failed GPU
starts. Precompute takes a few hours of laptop time.

### ADR-011: The main model is chosen by measurement in M2
**Status:** proposed (2026-10-21); M2 accepts it with the chosen model
**Context:** The 2026 small-model landscape (Qwen3.5, Gemma 4) is
multimodal and partly non-standard (hybrid DeltaNet layers). Tooling
support for GRPO + LoRA + vLLM colocate isn't guaranteed.
**Decision:** Screen the candidates in TRAINING.md §1 against the criteria
there, with Qwen3-1.7B as the fallback.
**Consequences:** Possibly not the newest model, but one that trains.

### ADR-012: Public repo, pre-registered predictions, negative results reported
**Status:** accepted (2026-10-21)
**Context:** The CV value comes from credibility, and recruiters and ML
engineers can read the repo.
**Decision:** Predictions go into RESULTS.md before each experiment. Every
run, including failures, is in the ledger and the results. Nothing is
cherry-picked: the final checkpoint gets the test eval.
**Consequences:** Results may look less flashy, but they hold up.
