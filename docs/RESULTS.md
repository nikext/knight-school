# Results

Write **predictions before running** each experiment (CLAUDE.md), in the
"Predicted" column, committed before the launch. Measured values carry 95%
bootstrap CIs. Arm-vs-arm differences use a paired bootstrap. Model:
**Qwen3.5-2B**, non-thinking template (ADR-011, ADR-017).

## E0: knowledge probe (probe500, exact match %)

| Checkpoint | P1 square | P2 legal count | P3 FEN after move | P4 in check | Predicted |
|---|---|---|---|---|---|
| base (zero-shot) | 4.8% [1.6, 8.8] | 4.0% [0.8, 8.0] | 0.0% | 50.4% [41.6, 59.2] | P1 40–60%, P2 2–8%, P3 0–2%, P4 55–75% (written 2026-10-21, before any run) |
| base → GRPO dense (E2, config v1) | 1.6% [0.0, 4.0] | 3.2% [0.8, 6.4] | 0.0% | 50.4% [41.6, 59.2] | no change beyond noise (E2 predictions) |
| base → GRPO dense (E2, config v2) | 3.2% [0.8, 6.4] | 4.0% [0.8, 8.0] | 0.0% | 50.4% [41.6, 59.2] | no change beyond noise (E2 predictions) |
| primer-M | | | | | |
| primer-M → GRPO dense | | | | | |

Base row: `m2-screen-a100-r4`, `results/eval/probe500/qwen3.5-2b.md`. **It
mostly measures copying of the format hint, not knowledge.** Qwen3.5-2B
answers P1 with the hint's own example, `white knight`, on 106 of 125 items,
and P4 with `yes, by Qe7`, the P4 example, on all 125. P4 grades only the
yes/no word on a balanced set, so any constant answer scores about 50%
(Gemma 4 E2B says `no` on 121 and scores 48.0%). P1 missed the prediction by
a wide margin. The other screened models, for comparison: Qwen3-1.7B P1 11.2%,
P2 2.4%, P4 50.4%; Gemma 4 E2B P1 36.8%, P2 0.8%, P4 48.0%; P3 0% for all.
The primer-trained rows answer in the primer's formats, so they won't copy
the hint. Their gain over the base row is therefore partly a format gain.
Read E0 deltas with that in mind, or re-run the base row with example-free
hints (proposed for M3).

## E1: baselines (test2000 unless noted)

Predictions written 2026-10-21, before any test2000 run. Two harness smoke
tests had been run on dev500 by then: random on all 500 (1.0% solved) and
Stockfish 1k nodes on 100 puzzles (87%).

| Model | Predicted solve | Solve rate | Move acc | Legal rate | Puzzle rating | $ / 1k puzzles |
|---|---|---|---|---|---|---|
| random legal | ~1% | 0.8% [0.4, 1.2] | 7.0% [6.3, 7.8] | 100% | below range | 0 |
| Stockfish 1 node | 30–45% (rating ~1000–1300) | **68.6%** [66.6, 70.6] | 83.6% [82.6, 84.7] | 100% | 2109 [2059, 2160] | 0 |
| Stockfish 1k nodes | 85–92% (rating > 2400) | 88.8% [87.5, 90.2] | 94.8% [94.1, 95.4] | 100% | above range (57% in the 2600–2799 bin) | 0 |
| base model (zero-shot): Qwen3.5-2B | 2–8%, legal 60–90%, rating below range | 4.1% [3.2, 5.0] | 15.6% [14.6, 16.6] | 96.4% [95.8, 97.0] | below range | 0.03 (L4 generation only) |
| Gemini Flash-Lite | 5–15% | pending (after 2026-11-13, ADR-013) | | | | |
| Gemini Flash | 15–35% | pending (after 2026-11-13, ADR-013) | | | | |
| Gemini Pro (test500) | 30–55% | pending (after 2026-11-13, ADR-013) | | | | |
| Chess-R1, Qwen2.5-7B dense (reported, different set) | | | ~25–30% | | | — |

Engine rows: laptop, 2026-10-21, `results/eval/test2000/{random,stockfish-1node,stockfish-1k}.md`.
**Stockfish at 1 node missed the prediction by a wide margin** (68.6% vs
30–45%): `go nodes 1` is not one node. Stockfish always finishes its
depth-1 iteration (with quiescence search) before it checks the limit; on a
Scholar's-mate position it reported depth 2, seldepth 3, 48 nodes and found
the mate. That already resolves most short tactics.
Its per-bin solve rate falls from 99% (400–599) to 18% (2600–2799). That makes
"1-node Stockfish" a strong bar, not a weak one.

Base row: `m2-test2000-qwen35-l4` (spot L4, 2026-10-22),
`results/eval/test2000/qwen3.5-2b.md`, format re-graded under ADR-017
(format rate 100%). Solve rate is inside the prediction, and the legal rate
beat it: with the move list in the prompt, the model almost always copies a
legal move. It answers directly, in about 10 tokens, with no reasoning. Its
solve rate falls from 11–16% in the 400–799 bins to about 0 above 1800, so
it is close to random (0.8%) on hard puzzles and does better on easy ones,
where a check or capture from the list is often the answer. Move accuracy
of 15.6% against random's 7.0% means its picks are better than chance.
$/1k counts the 105 s of generation only; the job cost $0.13 with boot.

## E2 / E3: the main comparison (test2000)

| Arm | Predicted solve | Solve rate | Move acc | Legal | Δ vs E2-dense (paired) | Run $ |
|---|---|---|---|---|---|---|
| E2 base → GRPO sparse, v1 | 4–8% (point 6%); move acc 16–24%, legal ≥ 98% | not run: v1 dropped (ADR-021) | | | | $6.13, preempted to step 20 |
| E2 base → GRPO dense, v1 | 7–14% (point 10%); move acc 22–32%, legal ≥ 99% | **23.8% [21.9, 25.7]** | 41.8% [40.3, 43.3] | 100.0% | — | $7.84 + $0.29 eval |
| E2 base → GRPO dense, v2 | 22–33% (point 28%); see below | **27.2% [25.2, 29.1]** | 43.6% [42.1, 45.2] | 100.0% | reference for v2 arms; vs dense v1 +3.4 [1.8, 4.8] | $9.22 with both evals (attempt 1 a $0 stockout) |
| E2 base → GRPO sparse, v2 | 16–30% (point 24%); see below | **23.5% [21.6, 25.4]** | 38.7% [37.2, 40.3] | 98.1% | −3.6 [−4.9, −2.4] at step 200; dev500 steps 100–150: −0.3 [−2.0, 1.4] | $12.16 + $5.35 (resumed from step 180 as `-r2`) |
| E3 primer-M only | | | | | | |
| E3 primer-M → GRPO sparse | | | | | | |
| E3 primer-M → GRPO dense | | | | | | |

**E2 predictions** (written 2026-10-22, before any GRPO run of the main model; the only
training signal seen so far is M2's 5-step compatibility smoke and the M3 laptop wiring test
on Qwen3.5-0.8B, whose numbers mean nothing). Base: 4.1% solve, 15.6% move acc, 96.4% legal.
- **Dense** gains several points, mostly on the easy bins (400–1199), in the first ~100 steps,
  then flattens: about 10% solve, well below Chess-R1's 25–30% plateau (a 2B model with LoRA,
  12.8k prompts, and no reasoning to start from).
- **Sparse** learns a little, unlike Chess-R1's 3B. The base model's per-sample move accuracy
  (~15%) leaves about half of the 8-sample groups with a correct move, so there's signal. Still,
  I'd put only even odds on its test2000 CI clearing the base model's. Dense beats sparse
  (paired Δ > 0).
- **Reasoning:** prose before `<answer>` stays rare (< 10% of completions at the end), and
  completions shrink to ~10 tokens. A rambling completion that is cut off gets 0 reward, and
  neither reward pays for thinking directly. This is the prediction I'm least sure of.
- **E0 on the dense checkpoint:** no change beyond noise on P1–P4 (RL on move choice doesn't
  teach board reading).

**E2 dense, config v1** (`m3-e2-dense`, ADR-019; test2000 from `m3-e2-dense-eval-r3`,
`results/eval/test2000/m3-e2-dense.md`). The solve prediction missed badly on the low side:
23.8% against a predicted 7–14%, close to Chess-R1's 25–30% plateau rather than well below it.
Nearly all of the gain came in the first 25 steps (dev500 5.6% → 22.8%, then 22–28% to step
200). By bin, 74% of 400–599 puzzles and 21% of 1200–1399 are solved, falling to ~1–2% above
2400. The other predictions held: answers shrank to ~9 tokens with no prose, legal reached 100%,
and E0 didn't move (P1 1.6%, P2 3.2%, P3 0%, P4 50.4%, all within noise of the base row).
**The plateau is a collapse, not a ceiling:** mean token entropy fell from 0.88 to 0.056 by
step 25, and over steps 41–50 a mean of 74% of the 8-sample groups had zero reward spread, so
they gave no gradient (`results/train/m3-e2-dense/steps.csv`). That led to config v2 (ADR-021).
E2 sparse under v1 got to step 20 before preemptions ended it. Its training move-match rate
tracked dense's step for step (0.059 → 0.268 against 0.059 → 0.266 over steps 1–19), so the
"sparse learns little" prediction was already in doubt.

**E2 v2 predictions** (written 2026-10-22, before `m3-e2-dense-v2` launched; v1 dense is the
only main-model GRPO run so far):
- **Step-50 check, pre-registered** (ADR-021). Over steps 41–50 of `m3-e2-dense-v2`, v2 passes
  only if all of these hold: mean token entropy ≥ 0.10 (v1: 0.042), mean share of zero-spread
  groups ≤ 0.50 (v1: 0.74), dev500 solve at step 50 ≥ 19% (v1: 22.4% [18.8, 26.2]), dev500
  legal ≥ 98%, truncated completions ≤ 2%, and mean completion length ≤ 100 tokens. If any fails,
  the VM is stopped and v1 stays. I give the check about 65%: the controller should hold
  entropy near 0.2, but the bonus may land on format tokens or prose instead of move choice.
- **Step-50 check result (2026-10-22 20:15Z): PASS** on every criterion. Steps 41–50: mean
  entropy 0.197 (bar 0.10), zero-spread groups 37% (bar 50%), dev500 solve 22.8% and legal 99.5%
  at step 50, truncated 0.1%, mean length 10.3. The controller didn't stop the collapse: steps
  20–27 fell like v1, to entropy ~0.06 and 66% dead groups, while the coefficient ramped 0.02 →
  0.18. It pulled entropy back from step 28 and settled at a coefficient of 0.46 with entropy at
  the 0.2 target. dev500: 5.0, 4.8, 19.6, 23.8, 21.6, 22.8% at steps 0–50. v2 becomes the
  frozen config (ADR-021), and the run continues to step 200.
- **Dense v2** keeps learning after step 25 instead of flattening: dev500 at step 50 about 21%
  (it may start a little slower than v1), and test2000 22–33% (point 28%), about +4 points over
  v1 (paired). The gain over v1 is mostly in the 800–1599 bins. Completions stay short (mean
  ≤ 20 tokens). I'd put 25% on prose before `<answer>` reaching > 10% of completions by the end.
- **Sparse v2** learns, behind dense: 16–30% (point 24%), paired Δ vs dense v2 about −4 points,
  with a CI that may include 0. This drops the original "sparse ≈ flat, replicates Chess-R1"
  expectation (RESEARCH.md E2) on the strength of v1's first 19 steps.

**E2 dense, config v2** (`m3-e2-dense-v2`, ADR-021; `results/eval/test2000/m3-e2-dense-v2.md`,
`results/train/m3-e2-dense-v2/`). test2000: 27.2% [25.2, 29.1] solve, 43.6% move accuracy, 100%
legal, puzzle rating 1011 [967, 1053] (v1: 873). Paired against v1 on the same 2000 puzzles the
gain is +3.4 points [1.8, 4.8]: v2 alone solves 145 puzzles, v1 alone 78. The point prediction
(28%, about +4) held, but the evidence for it is weaker than the CI suggests:
- **The dev plateau didn't move.** dev500 averaged 26.4% over steps 150–200 (six evals), and v1
  averaged 27.0% (steps 150, 175, 200). v1's last checkpoint sat on a dev dip (25.2% at step 200,
  28.0% at 150) and v2's on a peak (29.0% at 200), so part of the test gap comes from where each
  run stopped. The paired CI covers puzzle sampling, not seed or checkpoint variance, and each
  config has one seed. I read this as v2 ≥ v1, not as a 3-point gain.
- **The gain is in the easy bins**, not in 800–1599 as predicted: +14, +7, +8, +10 and +5 points
  across the 400–1399 bins, and within ±2 points in every bin from 1400 up.
- **More learning signal, same ceiling.** Over steps 31–90, v2 held mean entropy at 0.19 with
  46% dead groups. v1 had 0.04 and 72%. Yet dev500 sat at 22–25% in both runs. So a steady
  supply of gradient wasn't what held v1 at its plateau. That fits the primer premise: the model
  is short of board knowledge, and E0 didn't move (P1 3.2%, P2 4.0%, P3 0%, P4 50.4%). It is
  one run, though.
- **Known flaw: post-answer rambling switched the bonus off.** From about step 85, 0.5–2% of
  completions give a valid `<answer>` and then run on to the 1024-token cap with loose
  "step-by-step" text after `</answer>`. The reward has already scored the answer, so nothing
  penalises the extra text. TRL's controller measures a token-weighted entropy over the whole
  step, so this ~1% of completions carries about 40% of the tokens (steps 81–200), and their high
  entropy reads as above target. On the 40 steps with ≥ 0.5% of completions truncated, the
  coefficient didn't rise on 37. On the 65 steps with none truncated, it rose on 42. The
  coefficient stayed near 0 from step 94 to 135, and dead groups climbed to 70–80%. Logged
  entropy, a per-micro-batch mean, still read 0.11–0.15. The coefficient recovered to 0.38 by
  step 154 and fell to 0 again from step 190. Mean length stayed ≤ 32 tokens and prose before
  `<answer>` stayed at 0, so none of the step-50 criteria could catch it. A fix would stop
  generation at `</answer>` or mask the post-answer tokens. That makes a third config, so v2
  stays frozen for comparability (ADR-021).
- **The rest of the predictions:** completions stayed short (mean 10–32 tokens per step), and
  prose before `<answer>` stayed under 0.1% of completions, so my 25% bet on > 10% lost.

**E2 sparse, config v2** (`m3-e2-sparse-v2`, finished as `m3-e2-sparse-v2-r2`;
`results/eval/test2000/m3-e2-sparse-v2-r2.md`, `results/train/m3-e2-sparse-v2/`, which merges both
ids). test2000: 23.5% [21.6, 25.4] solve, 38.7% move accuracy, 98.1% legal, puzzle rating 917
[873, 958]. Paired against dense v2 it is −3.6 points [−4.9, −2.4], against dense v1 −0.3
[−2.0, +1.5], and against the base model +19.4 [+17.5, +21.3]. The first job reached its 4-hour
wall clock at step 186 (exit 124, not a preemption; $12.16). `m3-e2-sparse-v2-r2` resumed from a
server-side copy of checkpoint 180 and ran steps 181–200 plus test2000 ($5.35). Steps 181–186
were therefore paid for twice (~$0.9). The committed eval file cuts each response to its first
300 characters to fit the repo's 1 MB limit. Its header explains the cut, and the full file
stays in GCS until M6.
- **Point predictions met, but for the wrong reason.** The 24% point and the −4 gap vs dense
  both landed (my "CI may include 0" didn't: it doesn't). But up to step 150 sparse matched dense.
  From step 30 to 150, dev500 ran 24.0–27.4% for sparse and 21.6–28.8% for dense v2. Paired on the
  same 500 puzzles and averaged over the six evals at steps 100–150, sparse − dense = −0.3 points
  [−2.0, +1.4]. The step-200 gap comes from what happened after step 150, not from the reward.
  While both arms were healthy, the dense Stockfish reward added nothing over the 0/1 move reward.
  The per-sample move-match rate in training (T = 1) rose from 0.06 to 0.44–0.47 (mean over steps 151–200) in all three runs.
- **From step 150 it blew up into post-answer rambling.** At step 150, 1.6% of completions ran to
  the 1024-token cap. That share was 31% at step 155, 72% at step 160, and 83–96% from step 165 to
  200, with mean length about 950 tokens. Every logged completion from step 170 on closes
  `</answer>` at character 11 and then writes a made-up "explanation" until the cap. Under greedy
  decoding it is the same: 99.8% of test2000 answers hit the cap, so the eval took 369 s instead
  of 26 s. Step time went from ~40 s to 170–210 s, which is what used up the first job's
  4 hours. Logged entropy rose to ~0.9, all of it from the rambling. The coefficient sat at 0 and
  ~90% of groups were dead. A smaller episode at steps 45–60 (up to 10% truncated) had recovered.
- **The rambling froze the answer.** Between dev evals at steps 140 and 150, 99 of 1163 greedy
  answers changed. Between 160 and 170 it was 11, and from 170 to 200 it was 2–4 per 10 steps.
  dev500 read 24.2% at all five evals from step 160 to 200. This fits the loss arithmetic. The
  DAPO loss averages over every completion token, and the ~5 answer tokens are ~0.5% of a
  1024-token completion, so the move choice got almost none of the gradient. The tail cost time
  and also stopped learning. Answers came out slightly worse too: legal 98.1% against 100%, and
  move accuracy 38.7% against dense v2's 43.6%.
- **Nothing anchors the tokens after `</answer>`.** The reward never reads them, truncated
  completions keep their reward (`mask_truncated: false`), and the KL term (β = 1e-3) is weak.
  Each rambling completion's advantage is its answer's, spread over far more tokens. Dense v2
  had the same 0.5–2% tail from step 85 and never took off. With one run per arm, I can't say
  why sparse took off at step 150 and dense didn't. The arms share every other setting, so it
  may be chance.

**E2 reading.** GRPO on the base model lifts test2000 solve from 4.1% to 23.5–27.2% under every
reward and config tried (dense v1 23.8%, dense v2 27.2%, sparse v2 23.5%). dev500 reaches its
plateau by step ~25 (about $2) and stays at 21.6–29.0% from there to step 200. Neither more learning signal
(v2's entropy control) nor a denser reward lifted that plateau while the runs were healthy.
E0 didn't move either. That is the starting point H1 tests. The open problem for M4 is
the post-answer tail in config v2, which cost sparse its last 50 steps and pulled dense v2's
entropy controller off.

Figures (E2): dev500 solve rate vs dollars spent for all three runs
(`results/figures/e2_dev_vs_usd.png`), and training metrics per step: move-match rate, legal and
format rates, length, truncated share, prose share, entropy, dead groups and KL
(`results/figures/e2_components.png`). M4 adds the E3 arms and a per-bin figure
(`results/figures/e3_bins.png`).

## E4: primer scaling (test2000, GRPO dense)

| Primer | Tokens | Predicted | Solve rate | Run $ |
|---|---|---|---|---|
| none (E2) | 0 | | | |
| S | ~15M | | | |
| M (E3) | ~150M | | | |
| L | ~450M | | | |

## E5: ablations

| ID | Arm | Predicted | Result | Run $ | Status |
|---|---|---|---|---|---|
| E5a | rules-only primer → GRPO dense | | | | |
| E5b | no legal-move list | | | | |
| E5c | ~4B model, best recipe | | | | |
| E5d | LoRA r=8 vs r=64 | | | | |

## Hypothesis verdicts

| | Verdict | Evidence |
|---|---|---|
| H1 | | |
| H2 | | |
| H3 | | |
| H4 | | |
| H5 | | |

## Cost summary

| Pool | Ceiling | Spent | Biggest line items |
|---|---|---|---|
| compute | 360 | | |
| vertex | 180 | | |
