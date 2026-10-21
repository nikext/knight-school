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
- Models with native thinking use it in place of `<think>`. Decide once in
  M2 (ADR) and keep it for every arm.
- **Parser** (`ks.chess.parse`): take the last `<answer>…</answer>`, strip
  it, and resolve it with `board.parse_san`. Tolerate a missing `+`/`#` and
  `0-0` for `O-O`. It must be in the legal list, otherwise the move is
  illegal. Unit-test it thoroughly; it is the most-called code in the repo.

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
| max completion tokens | 1024 | lower it if p95 length is far below |
| temperature | 1.0 | |
| KL β | 1e-3 | Chess-R1; `loss_type` per TRL's current default, recorded in an ADR |
| steps | 200 | about 12.8k prompts; extend only if the dev curve is still rising and the budget allows |
| dev eval | every 25 steps on dev500, greedy | |

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

## 6. Hardware

| Job | Machine | Note |
|---|---|---|
| unit tests, parser, rewards, tiny-model smoke | laptop (RTX 3060 6 GB) | free; use a ≤ 1B model for wiring tests |
| GRPO smoke, small evals | `g2-standard-8` (L4 24 GB) spot | ~$0.30/h |
| SFT and GRPO runs | `a2-ultragpu-1g` (A100 80 GB) spot | default |
| | `a3-highgpu-1g` (H100 80 GB) spot | only if M3 measures a lower $/step |

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
  Build with Cloud Build if its free tier covers it (verify), otherwise
  locally with podman and push.

## 9. Run config (`configs/runs/*.yaml`)

```yaml
id: m3-e2-dense-r1
milestone: M3
pool: compute
backend: gce                  # gce | vertex
machine: a2-ultragpu-1g
zones: [us-central1-a, us-central1-b, us-central1-c, us-central1-f]
max_hours: 12                 # hard VM limit (max-run-duration)
run_budget_usd: 30            # approved total across preemption retries
image: train:<git-sha>
command: [python, -m, ks.train.grpo, --config, configs/train/grpo_dense.yaml]
inputs: [gs://BUCKET/data/v1/positions/rl_train.parquet]
outputs: gs://BUCKET/runs/m3-e2-dense-r1/
```
