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
**Status:** accepted (2026-10-22, the user chose it in the M2 session): the main model is
**Qwen3.5-2B** (`configs/models/qwen3.5-2b.yaml`, `Qwen/Qwen3.5-2B` @ `15852e8c1636`)
**Context:** The 2026 small-model landscape (Qwen3.5, Gemma 4) is
multimodal and partly non-standard (hybrid DeltaNet layers). Tooling
support for GRPO + LoRA + vLLM colocate isn't guaranteed.
**Decision:** Screen the candidates in TRAINING.md §1 against the criteria
there, with Qwen3-1.7B as the fallback. Screening ran as `m2-screen-a100-r4`
(one spot A100 80GB, 43 min, $2.22; `results/eval/dev500/`,
`results/screen/m2-screen-a100-r4/`). dev500, greedy, 1024 tokens, format
graded per ADR-017:

| Candidate | GRPO smoke (5 steps) | Legal & formatted | Solve | Move acc | Prompt tok | License |
|---|---|---|---|---|---|---|
| **Qwen3.5-2B** (tags) | runs, 5.5 s/step, reward std > 0 | **96.5%** | 5.4% | 15.9% | 218 | Apache-2.0 |
| Qwen3-1.7B (tags) | runs, 3.0 s/step, reward std > 0 | 67.2% | 5.8% | 10.2% | 218 | Apache-2.0 |
| Gemma 4 E2B (tags) | runs, 9.5 s/step, every completion clipped at 512, reward 0 | 20.5% | 0.4% | 4.0% | 202 | Apache-2.0 |
| Qwen3.5-2B native thinking | not run | 0% (100% hit 1024 tokens) | 0 | 0 | 211 | |
| Qwen3-1.7B native thinking | not run | 0% (100% hit 1024 tokens) | 0 | 0 | 209 | |

Qwen3.5-2B wins criteria 1–3 and ties on 4. Gemma 4 E2B fails criterion 2
and gives GRPO no signal (it reasons past any budget). Qwen3-1.7B stays the
fallback.
**Consequences:** The starting policy answers directly in about 10 tokens
(ADR-017), so RL rollouts are short and cheap, and any reasoning has to
emerge during RL. Peak GPU memory in the smoke (38.8 GiB) is mostly vLLM's
45% reservation on the 80 GB card, so it says nothing about fitting an L4;
M3 measures that.

### ADR-012: Public repo, pre-registered predictions, negative results reported
**Status:** accepted (2026-10-21)
**Context:** The CV value comes from credibility, and recruiters and ML
engineers can read the repo.
**Decision:** Predictions go into RESULTS.md before each experiment. Every
run, including failures, is in the ledger and the results. Nothing is
cherry-picked: the final checkpoint gets the test eval.
**Consequences:** Results may look less flashy, but they hold up.

### ADR-013: Two real credits, one expiring 2026-11-12: front-load GPU work, Gemini after
**Status:** accepted (2026-10-21, approved by the user in the M0 session)
**Context:** The plan assumed open-ended "$400 GCP + $200 Vertex" credits.
Billing → Credits showed something else. One credit is the Google Developer
Program annual credit, $440.94 left, covering all of Google Cloud, which
**expires 2026-11-12**. The other is "Marketing – GDP Premium Support 4",
$209.26 left, expiring 2027-04-08, with scope "certain usage". The user
could not open its terms, but past Gemini spend came out of it. Both credits
are shared with the user's other projects. Spot prices (measured in M0) are
about 70% above the third-party figures the plan used.
**Decision:**
- `compute` pool = the annual credit, ceiling $360 (= min(360, 0.9 ×
  440.94)). The gate refuses any job whose worst-case end is less than 48 h
  before expiry, so **all GPU work must end by 2026-11-10 00:00Z**. That
  includes M6's final evals. Sessions run every ~2–3 days, and M5 shrinks to
  whatever fits.
- `vertex` pool = the Marketing credit, ceiling $180, scope **assumed**
  Gemini-only. Custom training is assumed not covered, so the Vertex
  backend stays a stub and the vertex M5 line is dead. Gemini baselines
  move out of M2 to after the annual credit expires (`usable_from:
  2026-11-13`), so they cannot eat compute credit. They start with a 1-cent
  scope test checked in Billing → Reports. Before then, the only Vertex spend
  is the M0 smoke call.
- The bucket and registry are emptied by 2026-11-11 unless the Marketing
  credit is shown to cover storage. Data stays on the laptop, and models go
  to Hugging Face only with the user's yes.
- The credit snapshot in caps.yaml must be re-read weekly. Other projects
  draw on the same credits, so the gate also caps the worst case at 0.9 ×
  remaining credit minus our spend since the reading (ADR-014).
**Consequences:** Roughly 118 A100-hours at most, and a tight calendar. If the
GDP subscription renews and a new credit appears, the user updates
caps.yaml and this ADR gets a successor. The `ks-net` budget plus the kill
switch (billing detach at $5 net) is the backstop if a credit runs out
early.

### ADR-014: Gate additions in M0: credit window, credit headroom, one job at a time, CPU-only VMs
**Status:** accepted (2026-10-21)
**Context:** BUDGET.md §3.3 listed the original gate rules. M0 found three
gaps. The credits expire (ADR-013). They are shared with other projects, so
the caps.yaml ceiling can be wrong without anyone editing it. And the
kill-switch test needs a labelled VM that has no GPU.
**Decision:** On top of BUDGET.md §3.3, `ks.cloud.gate.check()` also refuses
when:
- the pool's credit is not yet usable (`usable_from`), or the job's
  worst-case end is within `expiry_margin_hours` (48) of `expires`;
- the credit reading is missing or older than 7 days;
- `worst_case > 0.9 × remaining_usd − spent_since(checked_on) − running`;
- any other attempt in the pool is still open (one job at a time; this
  also catches double launches);
- a fresh run reuses an id, or a retry doesn't follow the last attempt;
- the run id doesn't start with its milestone, or the machine's GPU count
  differs from the run's `gpus`.

Machines may have **at most** one GPU rather than exactly one, so a CPU-only
spot VM (`e2-standard-2`, priced like any other machine) can be launched for
infra tests. Worst cases round up to 1/100 cent.
**Consequences:** 44 gate tests. A CPU VM still goes through every money rule.
"Exactly 1 GPU" in ADR-002 now reads "at most 1 GPU". The no-multi-GPU
intent is unchanged.

### ADR-015: M1 data conventions: orderings, splits, reward settings, primer format
**Status:** accepted (2026-10-21)
**Context:** DATA.md left several choices to M1 ("decide once, never
change"), and some facts had to be checked against the real files and the
engine.
**Decision:**
- **Stockfish 19**, the official universal x86-64 build (from 19 on, one
  binary dispatches AVX2/BMI2/AVX-512 at runtime; no per-CPU build exists).
- **Legal-move order:** code-point order of SAN (`sorted()`), which puts piece
  moves first and pawn moves last. **Prompt FEN:** python-chess `board.fen()`.
- **Splits:** order by `sha256("2026:" + PuzzleId)`, not a library RNG, so
  they don't depend on polars or Python versions. Eval sets take at most one
  puzzle per game. (After filtering, every puzzle comes from a distinct game
  anyway.) Bin quotas give the remainder to the lower bins.
- **rl_train:** 66k positions before the mismatch filter, drawn bin by bin,
  with blocklisted and duplicate keys dropped. primer_pool excludes the
  rl_train *games*, not just the puzzles.
- **Reward tables:** `go nodes 1,000,000`, the largest timed N that fits in
  4 h. A `ucinewgame` before each position (hash cleared) makes the tables
  reproducible. The wp formula clamps cp to ±1000 like lila.
- **Primer:**
  - Weights count examples, not tokens.
  - T1–T5 take half their positions from primer_pool puzzle positions and
    half from the eval DB. T6 and T7 need an engine score and PV, so they
    use the eval DB only.
  - T5 on a puzzle position answers with the puzzle solution.
  - Every source position is used at most once.
  - An item is dropped if any position it shows or reveals (T3's result,
    T5's move, T7's line) is blocklisted, or is an rl_train position. The
    second rule keeps RL's contribution separable (H5).
  - **T5's prompt includes the RL prompt's `Legal moves:` line.** The other
    tasks don't, since T2 asks for that list.
  - Answers carry no `<answer>` tags; TRAINING.md §5's format-risk rule
    stays the fallback.
  - Half of T4's check questions go to positions that are in check.
  - T3 picks castling, ep or a promotion 30% of the time when one is legal.
  - **primer-S is the first 130k examples of primer-M** (nested), so the
    scaling curve changes only the amount of data.
- **probe500 reuses the primer generators** (P1 = T1 square, P2 = T2 all,
  P3 = T3, P4 = T4 check, with P4 balanced 63/62), so a primer checkpoint is
  probed in the exact format it was taught.
**Consequences:** All of these are frozen with data v1. Changing any of
them means data v2 and new manifests. M2's prompt builder and grader must
import `ks.chess.board` rather than re-implementing it.

### ADR-016: M2 stack pins, one image built by Cloud Build, open-model evals on the L4
**Status:** accepted (2026-10-21)
**Context:** ADR-004 asked for torch, vLLM and TRL to be pinned together.
On 2026-10-21 PyPI had vLLM 0.32.0, but TRL 1.16.0 declares
`vllm>=0.22.0,<=0.31.0`; vLLM 0.31.0 pins torch 2.13.0 and wants
transformers `>=5.10.4,<5.18`. The plan also hoped to screen ≤ 2B models on
the laptop. In practice the RTX 3060 (6 GB, shared with the desktop) left
vLLM 0.39 GiB of KV cache for Qwen3-1.7B in bf16: about 1.4 concurrent
sequences, so dev500 would take hours. vLLM's FlashInfer sampler also
JIT-compiles with nvcc, which the laptop doesn't have.
**Decision:**
- Pins: vLLM 0.31.0, torch 2.13.0, transformers 5.17.0, TRL 1.16.0, PEFT
  0.21.2, accelerate 1.15.0 (the `train` extra; `docker/requirements.txt`).
- One image `train:<git-sha>` on `vllm/vllm-openai:v0.31.0-x86_64-cu129`
  (pinned by digest), built by Cloud Build from `git archive HEAD`
  (`make image`), so an image is exactly one commit. Free tier: 2,500
  e2-standard-2 minutes a month, then $0.006/min.
- The image keeps the base image's torch, vLLM, triton, FlashInfer, numpy,
  numba and opentelemetry versions (pip constraints), and the build fails if
  `pip check` reports a conflict the base didn't have. The first build had
  let pip upgrade numpy to 2.5 under numba's `<2.5` pin; freezing the whole
  base failed instead, because its fsspec is newer than any `datasets` allows. The base ships
  google-api-core 2.40 with opentelemetry-api 1.40, which already disagree,
  so google-cloud-storage is left out of the image; jobs read GCS through
  `ks.cloud.gcs` (JSON API + google-auth).
- The laptop runs wiring smokes only (Qwen3-0.6B, `enforce_eager`,
  `VLLM_USE_FLASHINFER_SAMPLER=0`) plus the free engine baselines. Every
  open-model number comes from a `ks launch` eval job on a spot L4. No
  quantized screening, so screening and headline numbers come from the same
  bf16 weights.
**Consequences:** About $0.5–1 per L4 eval job instead of $0. Bumping TRL
past 1.16 later means re-checking its vLLM range and rebuilding the image,
which needs a new ADR.

### ADR-017: Thinking mode: non-thinking chat template, think block optional in the format rule
**Status:** accepted (2026-10-22, the user chose it in the M2 session)
**Context:** TRAINING.md §2 asked for a closed think block before the
answer and left the native-vs-tags choice to M2. Screening found both
modes broken as specified. With `enable_thinking=false`, the Qwen3 and
Qwen3.5 chat templates end the prompt with an empty `<think>\n\n</think>\n\n`.
The model takes its thinking as done. Qwen3.5-2B answers `<answer>Qxb4</answer>`
straight away, and Qwen3-1.7B reasons in untagged prose. So the strict
rule graded 0% format for both, although Qwen3.5-2B's moves were 96.5%
legal. Native thinking never finished inside 1024 tokens (100% truncated,
0% answers). The traces spend hundreds of tokens decoding the FEN
character by character. Making native thinking work would need a budget
of several thousand tokens per rollout, which would multiply the cost of
every RL run (BUDGET.md §2 assumes about 10 runs).
**Decision:** Tags mode with the non-thinking template (`think: tags`,
`enable_thinking: false`) for every arm. A profile with
`template_closes_think: true` has its think block in the prompt already, so
format there means exactly one answer block and no stray tags. Prose
before `<answer>` is allowed. The prompt text and hash (`c728de49e119`)
stay frozen. The screening reports were re-graded from their saved texts
with `ks rescore` ($0); each report records the rescore. Solve rate, move
accuracy and legal rate don't change, only format does.
**Consequences:** The prompt's "think inside <think></think>" line no
longer matches what the model does. It stays because changing it would
change the frozen hash, and the format reward never required it after
this ADR. The base model has no chain of thought to start from. Whether
GRPO grows one, as prose before the answer, is something to watch in M3
(completion length). The comparison between arms is unaffected, since
every arm uses the same contract.

### ADR-018: GRPO implementation (M3): engine, LoRA targets, loss, checkpoints, preemption
**Status:** accepted (2026-10-22)
**Context:** TRAINING.md §4 fixed the stack (TRL GRPOTrainer, vLLM colocate, LoRA) and left the
details to M3. Building `ks.train.grpo` and running the laptop wiring test (Qwen3.5-0.8B) turned up
several things the plan didn't foresee.
**Decision:**
- **Pins unchanged** (ADR-016): TRL 1.16.0 was still the newest release on 2026-10-22. Added to
  the image and the `train` extra: `flash-linear-attention`/`fla-core` 0.5.2 and `tensorboardX`
  2.6.5. Without fla, transformers runs Qwen3.5's Gated DeltaNet layers in a reference PyTorch
  implementation ("correct but much slower"). fla is pure Python plus Triton, so the base
  image's torch and triton stay. `causal-conv1d` is source-only (it needs nvcc) and stays out;
  its fallback is one convolution.
- **Engine:** TRL 1.16 builds the colocated vLLM engine itself and passes neither
  `language_model_only` nor `enforce_eager`. `ks.train.grpo` passes both from the model profile.
  Without `language_model_only`, vLLM loads the vision tower and reserves memory for dummy image
  inputs, which left the 0.8B no KV cache at all on the laptop's 6 GB. The trainer and vLLM both
  load a local snapshot at the pinned revision, so model, tokenizer and engine match.
- **LoRA targets:** TRL loads Qwen3.5 as the full VLM class (`Qwen3_5ForConditionalGeneration`),
  so `target_modules="all-linear"` would also adapt the vision tower. The adapter goes on every
  `nn.Linear` of the language model instead: attention, DeltaNet projections and MLP, but not
  the LM head and not the vision tower. That's 21.6M parameters on the 0.8B, and the 2B count
  is in its run.json.
- **Loss and sampling:** TRL 1.16 defaults, recorded here because they differ from Chess-R1's
  verl setup. `loss_type: dapo` (token-level normalisation over the whole generation batch, no
  length bias), `scale_rewards: group`, ε = 0.2, one iteration per batch. The vLLM importance-
  sampling correction is on (`sequence_mask`, cap 3). The KL term is TRL's default
  bias-corrected estimator at β = 1e-3. `mask_truncated_completions: false`, because a
  completion that runs out of tokens has given no answer, and reward 0 is correct for it.
- **Rewards:** the task reward and `format` have weight 1. `legal` and the other task
  components have weight 0, so they're logged but don't train. Each completion is parsed once
  per step.
- **Dev eval** (every 25 steps, dev500): greedy, on the trainer's colocated engine after a
  weight sync, through the same harness as `ks eval`. The token limit is the training one.
- **Checkpoints:** HF Trainer saves every 25 steps (adapter, optimizer, scheduler, RNG, data
  position). Each one is copied to `gs://BUCKET/runs/<id>/ckpt/checkpoint-<n>/` with a
  `_COMPLETE` object written last, the newest 2 are kept, and an attempt resumes from the newest
  complete one. Laptop test: a SIGTERM after checkpoint 2, then a resume, reproduced the
  uninterrupted run's step-3 and step-4 rewards exactly.
- **Preemption:** on SIGTERM the job leaves a marker, pushes its metrics and exits 143. The VM's
  EXIT trap can then write `ended` before the shutdown script writes `preempted`. Before this
  fix, reconcile would have booked that as `failed`, and the watcher would not have retried.
  Now the startup script flags `ended` as preempted when the VM's metadata says so, and
  reconcile also treats a failed exit plus an audit-log preemption as a preemption. A spot
  create that GCE cancels mid-provisioning (`Operation was canceled`, seen in
  m3-smoke-l4-r2) moves on to the next zone after checking that no VM was created.
- **Per-step metrics** (`<out>/metrics/attempt-<n>.jsonl`, TensorBoard via tensorboardX): every
  reward component's mean and std, legal and format rate, completion length (mean, p95, max,
  clipped share), prose before `<answer>` (share and characters: the reasoning-emergence
  signal), KL, entropy, step, generation and training seconds and tokens/s, and $/step plus
  cumulative $ (wall time × spot price, carried across attempts).
**Consequences:** One more thing to re-check when TRL is bumped: the `vllm_generation.LLM`
patch and the `_last_loaded_step` attribute the dev eval sets. A frozen-config test keeps arms
from changing anything but their factor (`ks.train.config.ARM_KEYS`).

### ADR-019: GRPO config frozen for every arm; A100 by $/step; padding trimmed, micro-batches sorted
**Status:** accepted (2026-10-22; max_completion and the throughput runs chosen by the user in the M3 session)
**Context:** Task M3 §4–5: smoke the main model, measure A100 vs H100 by $ per step, tune the
memory and batch split, then freeze the config. Measured on Qwen3.5-2B, dense reward, the full
64 × 8 batch (`m3-smoke-a100`, `m3-tput-a100`, `m3-tput-h100`; `results/train/`):
- **The base model rambles when sampled.** At temperature 1.0, 42% of completions ran into the
  1024-token cap, mostly prose that decodes the FEN character by character (cf. ADR-017). The
  legal rate was 53% (96.5% greedy). RL trained it away within ~10 steps: by step 13 the mean
  length was 18 tokens, legal 87%, format 99.6%, prose before `<answer>` < 1%.
- **Padding, not generation, set the step time.** Generation took 7–30 s a step. TRL pads all
  512 completions to the longest, and ~1% still hit the cap at step 13, so a step stayed at
  ~127 s on the A100 at an 18-token mean.
- **A100 vs H100**, same image, config and seed, before sorting (micro_batch 8, trimming on):
  steps 2–7 took 159 s vs 87 s ($0.138 vs $0.153 a step), and steps 8–10 took 98 s vs 55 s
  ($0.085 vs $0.097). The H100 is 1.8× faster at 2.05× the price. Trainer init took 218 s vs 86 s.
  With trimming, the A100's step at an ~20-token mean fell from 127 s to 62 s.
- Memory on the A100 80GB: peak ~40 GiB (mostly vLLM's 45% reservation), 44.5 GiB in use.
**Decision:**
- **Machine: `a2-ultragpu-1g` (A100 80GB spot)**, 10–13% cheaper per step. The H100 is the
  fallback when the A100 is stocked out or the calendar is tight (1.8× faster per step).
  Zones: us-central1-a/-c, then europe-west4-a/-b.
- **Frozen config** (`configs/train/grpo.yaml`; arms may change only `ARM_KEYS`, enforced by
  `tests/test_train_config.py`). It is TRAINING.md §4's starting point, unchanged:
  LoRA r = 32, α = 64 on the language model's linear layers (ADR-018); lr 1e-5, 10 warmup steps,
  then constant; 64 prompts × 8 completions; temperature 1.0; β = 1e-3; `loss_type: dapo`;
  **max_completion 1024** (the user's choice, so that reasoning can still emerge in any arm);
  200 steps; dev500 every 25 steps; checkpoints every 25; seed 2026.
- **Efficiency only, exact:** `micro_batch: 32` (was 8); `vllm_mem: 0.45`. Each log-prob pass
  drops the right padding of its chunk (`ks.train.trim`; tested equal to TRL's log-probs and
  entropies). The step's micro-batches are cut from the batch sorted by completion length,
  in place of TRL's random shuffle. Under `dapo`, each micro-batch's loss is its token sum over
  the whole generation batch's token count, so the accumulated gradient doesn't depend on the
  grouping. The sorted, larger micro-batch is first measured in E2. If it runs out of memory,
  micro_batch drops back to 16 or 8 for every arm; that doesn't change the arms' math.
- Per run (A100, before the sorting gain is measured): ~14 min to the first step, ~25 min for
  the first ~10 (rambling) steps, then 190 steps at 20–60 s. That's **~2–4 h and $6–13 a run**,
  against BUDGET.md §2's $17–34. If an arm grows long reasoning, its steps go back toward the
  early ~150 s ($0.14 a step); `max_hours` caps that.
**Consequences:** M3 underruns its line. The re-plan (PLAN.md) prices M4/M5 with these numbers.
Changing anything in `grpo.yaml` after E2 starts invalidates the comparisons and needs a new ADR.
TRL's padding and shuffling are now patched (`ks.train.trim`), so a TRL bump must re-run
`tests/test_train_trim.py`.

### ADR-020: A $0 stockout is waited out within the run's approval; A100 zone order
**Status:** accepted (2026-10-22; the user approved waits of up to 12 h in the M3 session)
**Context:** On the afternoon of 2026-10-22, E2 sparse used 9 attempts over two run ids
(`m3-e2-sparse`, `m3-e2-sparse-r2`) and $6.13 and reached step 20. Its VMs lived 4–41 min
before preemption (about 10 min typically), while a fresh attempt needs ~16 min before its first
useful step: ~9 min of boot, docker install and image pull, ~3.7 min of trainer init, and a
~4.7 min first step at the base model's 450-token completions. 7 of the 8 VMs landed in
us-central1-a, the first zone in the list. Then every zone stocked out, which ended the run, and
the gate wants a new run id and a new yes for attempt 1. Spot A100 80GB quota exists only in
us-central1 and europe-west4, where `a2-ultragpu-1g` is offered in us-central1-a, us-central1-c
and europe-west4-a only. `europe-west4-b`, in every A100 config so far, doesn't offer the machine.
**Decision:**
- A stockout in every zone closes the attempt as `not-created` at $0 with `note: stockout`;
  any other create error gets `note: create failed` and is never retried.
- `stockout_wait_hours` per run config (default 0, at most 12, the user's limit): `ks watch`
  retries a stockout every 15 min for that long, counted from the first stockout in a row. It
  also picks up a first-attempt stockout from `ks launch --watch`. A run's approval covers
  these $0 retries, as it covers its preemption retries.
- `max_attempts` counts attempts that created a VM. A hard cap of 60 ledger attempts per run
  stops a retry loop that has gone wrong. The gate still checks the run budget, `max_hours`
  and the 2026-11-10 deadline on every retry.
- A100 zone order: us-central1-c, europe-west4-a, us-central1-a.
**Consequences:** one approval can run unattended overnight while the laptop stays awake (the
watcher runs there). That matters most for M4's 7–10 h SFT run. A long stockout leaves up to
~100 `start`/`end` lines in the ledger; they cost $0. Not done: baking docker into a custom VM
image (saves ~4 min a boot, but adds a billable image to manage), and asking for A100 quota in
us-east4/us-east5 (3 more zones; the user's call if capacity stays this bad).

### ADR-021: GRPO config v2: adaptive entropy control (supersedes ADR-019's frozen config)
**Status:** accepted (2026-10-22; the user chose one bounded revision before M4). Step-50 check
passed 2026-10-22 (RESULTS.md, E2 v2), so v2 is the frozen config for every later arm.
**Context:** E2 dense under ADR-019 (`m3-e2-dense`) reached 23.8% [21.9, 25.7] on test2000
(base 4.1%), but the policy collapsed by step 25. Mean token entropy fell from 0.88 (step 1)
to 0.25 (step 15) and 0.056 (step 25), then to ~0.02. Over steps 41–50 a mean of 74% of the
8-sample groups had zero reward spread, so zero advantage and no gradient. dev500 went
5.6% → 22.8% by step 25 and then stayed at 22–28% to step 200: steps 25–200 (~$6 of the
$7.84) taught little. Answers shrank to ~9 tokens with no reasoning. M4's main result (H1)
would run every arm under this config, so E3 would measure where each start point collapses,
and the GRPO baseline would be open to the charge of being undertuned. Chess-R1's 25–30%
plateau may be the same effect.
- **Clip-higher can't help here.** `num_iterations` is 1 and generation happens once per
  optimizer step, so the PPO ratio is exactly 1 and the clip never binds (TRL 1.16:
  `old_per_token_logps` is the same weights' log-probs). `epsilon_high`, first proposed to the
  user, was dropped after reading the TRL source.
- TRL 1.16 has an entropy bonus (`entropy_coef`) with adaptive control from Skywork-OR1
  (`use_adaptive_entropy`): each step the coefficient rises by `entropy_coef_delta` if mean
  token entropy is at or below `entropy_target` and falls otherwise, and applies only at or
  below the target. Chess-R1 used a static entropy bonus of 1e-3; ADR-019 had none.
**Decision:** v2 = v1 + `entropy_adaptive: true`, `entropy_target: 0.2`,
`entropy_coef_delta: 0.02`. Nothing else that shapes learning changes (lr 1e-5, 64 × 8,
T = 1.0, β = 1e-3, dapo, 200 steps, seed 2026).
- Target 0.2 is TRL's and Skywork's default, and also where v1 was still healthy: at steps
  15–17 answers were already ~10 tokens with ~9% dead groups. Delta 0.02 is 4× TRL's default
  because v1 fell from 0.2 to 0.06 in 6 steps; at 0.005 the coefficient would be 0.03 by then.
  The initial coefficient doesn't matter: above the target it decays to 0 within a few steps.
- Not learning settings: `eval_every` 25 → 10 (a finer dev curve, ~$0.2 a run) and
  `save_every` 25 → 10 (a preemption loses ≤ ~6 min).
- Bounded: one variant and one check. `m3-e2-dense-v2` is checked at step 50 against
  pre-registered criteria (RESULTS.md, E2). If it fails, the VM is stopped, v2 is dropped,
  ADR-019 stays frozen and E2 sparse runs under v1. If it passes, it runs to 200 and is E2
  dense, and E2 sparse and every M4/M5 arm use v2.
- Checked on the laptop (Qwen3.5-0.8B, forced ramp): the coefficient rises 0.02, 0.04;
  `entropy_ctrl_state.json` is copied with each checkpoint and restored on resume (0.06,
  0.08 after resuming from step 2).
- Found by the same smoke and fixed: resuming from a checkpoint at `max_steps` (a preemption
  between the last checkpoint and the final save) made `trainer.train()` run one step past
  it. The trainer now loads that adapter and saves the final model without training (the
  final adapter equals the checkpoint bit for bit).
**Consequences:** `m3-e2-dense` stays in the write-up as the v1 data point and the evidence
for the collapse; it isn't compared with v2 arms as if it were the same config. If v2 passes,
E2 costs one more dense run (~$8). `entropy_coef` is logged each step. Risk to watch: the
bonus applies to every completion token, so it could show up as noise on the format tokens
or prose before `<answer>`; format, legal, length and prose_frac are in the step-50 check or
next to it.
**Observed in `m3-e2-dense-v2`** (RESULTS.md, E2 dense v2): the risk showed up after `</answer>`,
where none of those metrics look. From about step 85, 0.5–2% of completions ran on to the
1024-token cap after a valid answer. TRL's controller measures a token-weighted entropy over the
whole step, and these completions carried ~40% of the tokens. They held it above target, so the
coefficient sat near 0 for steps 94–135, and dead groups climbed back to 70–80%. Test2000 was
still 27.2% (+3.4 [1.8, 4.8] paired vs v1) on the same dev plateau.
**Observed in `m3-e2-sparse-v2`** (RESULTS.md, E2 sparse v2): the same tail took over. Truncated
completions went from 1.6% at step 150 to 72% at step 160 and 83–96% after that. Step time rose
from ~40 s to 170–210 s, so the first job ran out of `max_hours` at step 186. The greedy answers
froze: 2–4 of 1163 dev answers changed per 10 steps, because the ~5 answer tokens are ~0.5% of a
1024-token completion under DAPO's token mean. test2000 came out at 23.5%, −3.6 [−4.9, −2.4]
vs dense v2 at step 200, although the two arms were equal on dev500 to step 150.
**So v2 has a real flaw for M4:** any arm can tip into this regime at random, which costs ~4× per
step and stops learning. The candidate fix, config v3, is v2 plus generation stopped at
`</answer>` (a stop string, kept in the output). It is to be decided by the user before M4's
first launch, and is not adopted here. v3 changes what the loss sees, so a clean H1 comparison
would need E2 dense re-run under v3 (~$9). Verify first that TRL 1.16 passes stop strings to
vLLM in colocate mode.
