# Training

## 1. Models (chosen by measurement in M2, ADR-011)

The main model is in the **1.5–2.5B class**. That is cheap enough for about 10
RL runs inside the budget (BUDGET.md §2). The best recipe is then confirmed
on the ~4B sibling (E5c). Candidates as of 2026-10; **verify the exact repo
names, licenses and tooling support on Hugging Face in M2**:

| Candidate | Notes |
|---|---|
| Qwen3.5-2B (instruct) | Feb 2026. A **vision-language** model with hybrid Gated DeltaNet + attention layers. Serve text-only (vLLM has a language-only mode, verify). Check that TRL + PEFT + vLLM colocate handle it, and which modules LoRA targets. |
| Gemma 4 E2B (instruct) | Mar 2026, Apache-2.0, multimodal. Check the same things. |
| Qwen3-1.7B | Apr 2025, plain text-only transformer, the most battle-tested tooling. This is the fallback if the newer ones fight the stack. |
| ~4B siblings (E5c) | Qwen3.5-4B / Gemma 4 E4B / Qwen3-4B-Instruct-2507 |

**Chosen in M2 (ADR-011): Qwen3.5-2B**, non-thinking template (ADR-017);
Qwen3-1.7B is the fallback. Gemma 4 E2B was dropped: it reasons past any
token budget (69% of dev500 answers truncated at 1024 tokens, every GRPO
smoke completion clipped at 512, reward 0).

Use **instruct** variants. Chess-R1's sparse-reward runs failed on base
models, and their instruct models improved more steadily.

Selection criteria (M2), in order:
1. A 5-step TRL GRPO + LoRA + vLLM-colocate smoke runs on the laptop or an
   L4 without hacks.
2. Zero-shot **legal-and-formatted rate** ≥ 50% on dev500 with the fixed
   prompt. RL needs some reward signal to start from.
3. Apache-2.0 or MIT license.
4. Prompt length in tokens. The FEN plus the legal-move list tokenizes very
   differently across tokenizers, and that cost is paid on every rollout.

## 2. Prompt and answer contract (shared by eval, RL and probes)

```
system: You are a strong chess player solving a puzzle.
user:   Position (FEN): r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4
        Side to move: White
        Legal moves: Bb3, Bb5, Bd3, …, Qxf7#, …
        Find the best move. Think it through inside <think></think>, then give
        exactly one move from the list, in SAN, inside <answer></answer>.
```

- The legal moves are sorted the way DATA.md §4 says. E5b drops that line.
- Models with native thinking use it in place of `<think>`. Decided in M2:
  the non-thinking template for every arm (ADR-017).
- **Parser** (`ks.chess.parse`, built in M2): the response ends at its first
  `</answer>` (ADR-022; generation stops there too). Take that
  `<answer>…</answer>` and normalise it: strip whitespace, `**`, backticks and
  quotes, a leading move number (`12.`, `12...`), a trailing period and
  `!`/`?` glyphs; tolerate a missing or extra `+`/`#` and `0-0`/`0-0-0`. The
  result must then equal a legal move's SAN (the prompt's list), otherwise
  the move is illegal. This is stricter than `board.parse_san`, which would
  also take long algebraic (`e2e4`) and null moves; the prompt asks for a move
  from the list. Format needs exactly one answer block and no stray tags,
  plus one closed think block before it (a native-thinking template may put
  the opening `<think>` in the prompt). If the profile says
  `template_closes_think` (the template pre-fills an empty, closed think
  block, as Qwen does with `enable_thinking=false`), no think block is
  needed (ADR-017). Unit-tested in `tests/test_chess_parse.py`.
- **Frozen in M2:** prompt hash `c728de49e119` (`think: tags`, legal list on)
  and `b371401fde1c` (`think: native`). `tests/test_chess_rewards_prompt.py`
  pins both; changing the text needs an ADR.

## 3. Rewards (`ks.chess.rewards`)

| Component | Value |
|---|---|
| `format` | 0.1 if exactly one well-formed answer (and think block if required), else 0 |
| `sparse` | 1 if move = solution, or it's the last solver move and the move mates; else 0 |
| `dense` | `wp(move)` from the reward table (DATA.md §6), in [0, 1] |
| `dense_norm` (variant) | `(wp − min wp) / (max wp − min wp)` over the legal moves |
| illegal / unparseable | task reward 0 (format reward may still apply) |

Total = task reward (`sparse` or `dense`, per run config) + `format`. Log
each component separately.

## 4. GRPO (`ks.train.grpo`)

- **Stack:** TRL `GRPOTrainer` (1.16.0 on 2026-10-15; pin the latest 1.x in
  M3) with vLLM in **colocate** mode on one GPU, PEFT LoRA, bf16, gradient
  checkpointing. Check TRL's docs for the vLLM version range it supports, and
  pin torch, vLLM and TRL together (ADR-004).
- **Starting hyperparameters**, adapted from Chess-R1. Tune only in the M3
  smoke, then freeze them for every arm:

| Param | Start | Why |
|---|---|---|
| LoRA | r=32, α=64, all linear layers | ADR-007 |
| learning rate | 1e-5, 10 warmup steps, then constant | about 10× Chess-R1's full-FT 1e-6 (LoRA Without Regret) |
| prompts per step | 64 | |
| generations per prompt | 8 | Chess-R1 used 8 |
| max completion tokens | 1024 | kept at 1024 (user, M3): the p95 was at the cap while the base model rambled, and 1024 leaves room for reasoning to emerge |
| temperature | 1.0 | |
| KL β | 1e-3 | Chess-R1; `loss_type` per TRL's current default, recorded in an ADR |
| steps | 200 | about 12.8k prompts; extend only if the dev curve is still rising and the budget allows |
| dev eval | every 25 steps on dev500, greedy | every 10 from config v2 (ADR-021) |
| entropy bonus | none (v1, ADR-019) | **v2 (ADR-021):** adaptive (Skywork-OR1, TRL `use_adaptive_entropy`), target 0.2, delta 0.02, because v1 collapsed by step 25 |
| stop | none (v1, v2) | **v3 (ADR-022):** stop at the first `</answer>`, kept in the output, because v2's post-answer tail ran to the cap |

- **Frozen config:** `configs/train/grpo.yaml`, v1 by ADR-019, revised to v2 by ADR-021 (its
  step-50 check passed in `m3-e2-dense-v2`) and to **v3 by ADR-022** (M4): every rollout stops
  at the first `</answer>`. Clip-higher (`epsilon_high`)
  is a no-op in this setup: one optimizer pass per generation batch keeps the PPO ratio at 1.
  Known limitation of v2: nothing stops generation after `</answer>`. In dense v2, the ~1% of
  completions that ran on to the cap held TRL's token-weighted entropy above target and
  switched the bonus off from step ~90. In sparse v2 that tail grew to ~90% of completions
  after step 150, steps took ~4× longer, and the answers stopped changing. v3 (ADR-022) adds
  the `</answer>` stop string, and both E2 arms are re-run under it in M4.

- **Logging per step:** each reward component (mean and std), legal rate,
  format rate, completion length (mean and p95), KL, entropy, generation and
  training tokens/s, step seconds, and **$ per step** (step seconds × price).
  Plot dev solve rate against **dollars spent**, not only steps. That makes
  the budget part of the story.

## 5. Primer SFT (`ks.train.sft`)

- **Full fine-tune** (ADR-007), bf16, AdamW (8-bit if memory needs it), lr
  1e-5 with cosine decay, 3% warmup, 1 epoch, packing on, **loss on the
  answer tokens only**, seq len 2048. Aim for about 0.25M tokens per optimizer
  step.
- Afterwards, save the merged model to GCS. GRPO puts its LoRA on top of
  this checkpoint.
- **Format risk:** the primer teaches short direct answers, and the RL prompt
  asks for `<think>`/`<answer>`. If the primer checkpoint's format rate on
  dev500 drops below 50%, add T8: about 2% of examples in the RL answer format
  with a short **templated** think block (checks, captures and threats
  listed by python-chess, still teacher-free). Record it in an ADR. The
  format reward then handles the rest.

**Frozen in M3 (ADR-019):** `configs/train/grpo.yaml` holds exactly the values above,
plus `micro_batch: 32` and `vllm_mem: 0.45`, which affect speed only. Arms change only the factor
under test (`ks.train.config.ARM_KEYS`, enforced by a test). Implementation details (engine
kwargs, LoRA targets, loss, checkpoints, preemption) are in ADR-018. TRL pads every completion
to the longest one in the batch, so `ks.train.trim` trims each chunk's right padding and cuts
micro-batches from the length-sorted batch. Both are exact; without them a step stayed at
~127 s on the A100 once completions were ~20 tokens.

**What the M3 smoke showed (`results/train/m3-smoke-a100`):** sampled at temperature 1.0, the
base model rambles. 42% of completions hit the cap, and the legal rate was 53% (96.5% greedy).
RL removed this in ~10 steps: by step 13 the mean length was 18 tokens, legal 87%, and format
99.6%.

## 6. Hardware

| Job | Machine | Note |
|---|---|---|
| unit tests, parser, rewards, tiny-model smoke | laptop (RTX 3060 6 GB) | free; use a ≤ 1B model for wiring tests |
| GRPO smoke, small evals | `g2-standard-8` (L4 24 GB) spot | $0.54/h; in M3 the L4 was stocked out in all six zones, so the smoke ran on the A100 |
| SFT and GRPO runs | `a2-ultragpu-1g` (A100 80 GB) spot | default |
| | `a3-highgpu-1g` (H100 80 GB) spot | M3: 1.8× faster per step, 10–13% more per step, so it's the fallback for A100 stockouts or a tight calendar (ADR-019) |

## 7. Checkpointing, preemption, resume

- Every ~15 minutes (GRPO: every 25 steps; SFT: by wall clock), write to
  `gs://$BUCKET/runs/<id>/ckpt/` and keep the last 2. LoRA adapters are
  small. Full-FT SFT keeps one optimizer state for resume and deletes it when
  the run finishes.
- Preemption gives about 30 s notice. Don't rely on it; rely on the periodic
  checkpoints. On SIGTERM, flush metrics and write a `preempted` marker.
- `ks launch --watch` relaunches a preempted run from its last checkpoint,
  trying other zones and then the fallback region. It stops when the next
  attempt's worst case would break the run's approved `run_budget_usd`
  (BUDGET.md §4).
- Every run writes `run.json`: git SHA, image digest, config hash, data
  manifest hashes, seed, library versions, machine, zone, attempt start and
  end times.

## 8. Container

- One image for SFT, GRPO and evals: built on a pinned
  `vllm/vllm-openai:<version>` image (torch + CUDA + vLLM), with TRL, PEFT,
  python-chess and this package added through uv.
- Stockfish is **not** in the image. Reward tables are precomputed (M1), which
  also keeps the GPL binary out of anything distributed.
- Tag `train:<git-sha>` and push to Artifact Registry in the GPU region.
  **Built with Cloud Build** (M2, ADR-016): the default pool's e2-standard-2
  has 2,500 free build-minutes a month per billing account, then $0.006/min
  (Catalog SKU A464-9020-6404); a build takes ~15–25 min. Pushing ~11 GB
  from the laptop would take far longer. Artifact Registry storage is $0.10
  per GB-month above 0.5 GB, about $1/month for one image; it is booked in
  the ledger as a `charge`.
- **Pins (M2):** base `vllm/vllm-openai:v0.31.0-x86_64-cu129` by digest
  (torch 2.13.0, CUDA 12.9, matching the DLVM image's driver 580), plus
  transformers 5.17.0, TRL 1.16.0, PEFT 0.21.2, accelerate 1.15.0
  (`docker/requirements.txt`, the `train` extra in pyproject.toml). TRL 1.16.0
  declares `vllm>=0.22.0,<=0.31.0` and vLLM 0.31.0 wants transformers
  `>=5.10.4,<5.18`.
- Files: `docker/Dockerfile`, `docker/cloudbuild.yaml`, `.gcloudignore`
  (uploads only what the image copies). The git SHA is baked in as
  `KS_GIT_SHA`, since the image has no `.git`.
- **M3 additions** (ADR-018): `flash-linear-attention`/`fla-core` 0.5.2 (Triton kernels for
  Qwen3.5's DeltaNet layers in training) and `tensorboardX` 2.6.5. TRL 1.16.0 was still the
  newest release on 2026-10-22, so the pins are unchanged.
- **Current image (M4, config v3 runs, ADR-022):** `us-central1-docker.pkg.dev/knight-school-nt26/knight-school/train:91af7e44bf9f@sha256:c377f7f110a18a69acf5361c37e267f4a8e3641f7e50b3a2a0f141854f106e48`
  (built 2026-10-23 from 91af7e4, 11 min 32 s on Cloud Build).
- **M3 image (config v2 runs, ADR-021):** `us-central1-docker.pkg.dev/knight-school-nt26/knight-school/train:35e9bf043759@sha256:8808004de26e22080fbc678338d6871a15af1f831588ce8c27a45782f0b0e01e`
  (built 2026-10-22 from 35e9bf0, 12 min 54 s on Cloud Build).
- **E2 v1 image (M3):** `us-central1-docker.pkg.dev/knight-school-nt26/knight-school/train:25b5dd417d43@sha256:b1127f781cb392cf18aa545759c02d90763c1d2403645a36a4f10c95f5004606` (`m3-e2-dense`, `m3-e2-sparse{,-r2}`).
- **Earlier image (M2):** `us-central1-docker.pkg.dev/knight-school-nt26/knight-school/train:90bfc56fc862@sha256:5750820ecc59b72928dc82f11db31cef6e5b5e404c69d12ac7b345e7437b7e7c`.
  It ran every M2 cloud number (screening on an A100 80GB, test2000 on an L4). It predates
  ADR-017's profile flag, so its reports were re-graded with `ks rescore`. M3
  needs a rebuild for its GRPO code anyway.

## 9. Run config (`configs/runs/*.yaml`)

```yaml
id: m3-e2-dense-r1
milestone: M3
pool: compute
backend: gce                  # gce | vertex
machine: a2-ultragpu-1g
zones: [us-central1-a, us-central1-b, us-central1-c, us-central1-f]
max_hours: 12                 # hard VM limit (max-run-duration)
max_attempts: 6               # attempts that created a VM (ADR-020)
stockout_wait_hours: 12       # ks watch retries a stockout every 15 min this long (ADR-020; <= 12)
run_budget_usd: 30            # approved total across preemption retries
image: train:<git-sha>
command: [python, -m, ks.train.grpo, --config, configs/train/grpo_dense.yaml]
inputs: [gs://BUCKET/data/v1/positions/rl_train.parquet]
outputs: gs://BUCKET/runs/m3-e2-dense-r1/
```
