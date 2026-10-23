# Research design

## 1. Question

Small LLMs trained with RL from verifiable rewards (RLVR) on chess puzzles
plateau low. **Can a cheap, teacher-free SFT "chess primer" raise that
ceiling?** Three sub-questions:

- **RQ1:** Primer → GRPO vs GRPO alone on the same base model: does the
  post-RL solve rate go up?
- **RQ2:** How does the post-RL solve rate scale with primer size (S / M / L
  tokens)?
- **RQ3:** What drives it: rules knowledge (board reading, legal moves, move
  effects) or Stockfish move imitation? And does the answer change with sparse
  vs dense reward?

Every training signal comes from python-chess or Stockfish. No LLM writes
training data (ADR-008).

## 2. Prior work (read before M2; cite in the write-up)

- **Chess-R1**: "Can Large Language Models Develop Strategic Reasoning?
  Post-training Insights from Learning Chess", arXiv:2507.00726 (KAIST &
  KRAFTON, 2025). Code: github.com/krafton-ai/Chess-R1 (Apache-2.0, verl).
  - Qwen2.5-3B/7B and Llama3.1-8B, GRPO in verl, 4× A100 80 GB, about 14 h
    per RL run. 19.2k position-action pairs from Lichess puzzles rated
    200–2800. Evaluated on 10k Lichess puzzles from Ruoss et al. (2024).
  - Prompt: FEN plus a list of legal moves in SAN. Output: one SAN move in
    `<answer>`, reasoning in `<think>`. In their ablations, **removing the
    legal-move list stopped learning**, UCI was clearly worse than SAN, and
    FEN vs PGN made little difference.
  - Rewards: sparse (move matches the solution) or dense (win probability of
    the move from a 270M action-value network, Ruoss et al.), plus a 0.1
    format reward. **Sparse failed completely for Qwen2.5-3B and Llama-8B.**
    Dense beat sparse.
  - Hyperparameters: 150 steps, lr 1e-6, 8 rollouts per prompt, batch 128,
    temperature 1.0, KL 1e-3, entropy 1e-3, clip 0.2.
  - Result: every model plateaued at **~25–30%** puzzle accuracy (an
    1800-Elo model gets 66.5%). Board-state prediction was 0% for all models.
    SFT on 1k o3 reasoning traces did not raise the plateau.
- **Shen et al.**, "Understanding Reasoning from Pretraining to
  Post-Training", arXiv:2607.16097 (Aug 2026). They pretrain 5M–1B models from
  scratch on human games, then SFT, then GRPO with binary rewards on puzzles.
  Pretraining validation loss predicts post-RL pass@1 (Spearman −0.99), and
  better pretraining also steepens the RL slope. RL amplifies moves SFT
  already preferred on easy puzzles and finds rare correct moves on hard ones
  ("tail discovery"). pass@16 often barely moves. → Our primer is a cheap
  stand-in for "better pretraining" on a general LLM. Report pass@k too.
- **Ruoss et al. (2024)**, "Amortized Planning with Large-Scale
  Transformers: A Case Study on Chess" (DeepMind, ChessBench /
  searchless_chess). A 270M transformer trained on Stockfish action-values
  reaches about 2300 Elo. This is the source of Chess-R1's critic and their
  10k-puzzle eval set.
- **"LoRA Without Regret"** (Thinking Machines, 2025). LoRA matches full
  fine-tuning for RL even at low rank, with an optimal LR about 10× full FT,
  but it falls behind on large SFT datasets. → LoRA for GRPO, full FT for the
  primer (ADR-007). Verify our own way in E5 if the budget allows.

- **C1 / "Grounded Chess Reasoning in Language Models via Master Distillation"**,
  arXiv:2603.20510 (Mar 2026; missed before M3). Qwen3-4B-Instruct-2507, near 0 at the start.
  SFT on ~39.6k puzzles whose chain of thought Gemini-3-Flash wrote around Stockfish (depth 24)
  lines, then DAPO with a binary "matches Stockfish's best move" reward (KL kept). The prompt has
  the FEN, a piece list and the legal moves. On their 900-puzzle set: 40.9% after SFT, 48.1%
  after RL. RL helps on beginner-to-advanced puzzles, not on expert ones. → The nearest prior
  result to H1/H2, but **with a teacher**: an LLM wrote the reasoning. Ours stays teacher-free
  (ADR-008), which keeps the question open. It also shows binary rewards learning after SFT
  (cf. H2).
- **VAM: Verbalized Action Masking**, arXiv:2602.16833 (Feb 2026). An exploration method for
  RL post-training, with chess puzzles as the case study. It repeats that the legal-move list
  matters. Not a change to the plan.

M3 re-search (2026-10-22, from 2026-10 on): no new LLM-chess RLVR result found. **The plan
is unchanged.**

## 3. Hypotheses and what would falsify them

| | Hypothesis | Falsified if |
|---|---|---|
| H1 | Primer → GRPO beats GRPO alone (dense) on test2000 | CIs overlap and the difference is < 3 points |
| H2 | With the primer, **sparse** reward learns at all, unlike Chess-R1's 3B | sparse reward on the primer model stays within noise of its start |
| H3 | Post-RL solve rate rises monotonically with primer size, roughly log-linear | the S→M→L curve is flat or non-monotonic |
| H4 | Rules-only primer recovers ≥ half of the full primer's gain | rules-only ≈ no primer |
| H5 | RL adds on top of primer-only SFT (it's not just Stockfish distillation) | primer-only ≈ primer → GRPO |

Write numeric predictions for each run in `docs/RESULTS.md` **before** running
it.

## 4. Experiments

All comparisons use the same base model (chosen in M2), the same GRPO config,
the same training positions and seeds, and the same eval sets. Only the
factor under test changes.

| ID | Arms | Eval | Notes |
|---|---|---|---|
| E0 | probe every model and checkpoint | probe500 | board reading, legal moves, move effect, check detection |
| E1 | random legal · Stockfish 1 node · candidate base models · Gemini Flash-Lite / Flash (test2000) · Gemini Pro (test500) | test | zero-shot, same prompt |
| E2 | base → GRPO sparse · base → GRPO dense | test + dev curves | expect sparse ≈ flat (replicates Chess-R1) |
| E3 | base → primer-M (SFT only) · primer-M → GRPO sparse · primer-M → GRPO dense | test + dev curves | the main result |
| E4 | primer-S → GRPO dense (M from E3; primer-L dropped in the M3 re-plan) | test | scaling curve over none, S, M: x = primer tokens (log) |
| E5a | rules-only primer (T1–T4, matched tokens to M) → GRPO dense | test | rules vs moves |
| E5b | E3-dense recipe, no legal-move list in the prompt | test | does the primer replace the crutch? |
| E5c | best recipe on a ~4B model | test | does it hold at a larger size? |
| E5d | LoRA rank 8 vs 64 for GRPO (optional) | dev | cheap check of ADR-007 |

**Seeds.** One seed per arm is affordable. To show the difference isn't seed
luck, the E3 headline arm (primer → dense) gets a second seed if M4 has the
money. Report the seed spread.

## 5. Threats to validity (address each in the write-up)

- **Contamination:** primer positions overlapping eval puzzles. The filter
  in DATA.md §5 is enforced by a CI test.
- **Eval noise:** 2,000 puzzles give a ±2 point CI at 30%. Use paired
  bootstrap for arm-vs-arm comparisons.
- **Prompt sensitivity:** use one fixed prompt for all arms, with the format
  in the report. E5b varies it on purpose.
- **Solution vs engine:** the Lichess solution and Stockfish's best move
  disagree on some positions. Measure the rate in M1 and report it.
- **Puzzle rating ≠ playing strength:** say so. Full games are a stretch
  item only.
- **The primer is distillation:** the move tasks (T5–T7) distill Stockfish.
  E5a separates rules from moves, and H5 checks that RL adds anything at all.
