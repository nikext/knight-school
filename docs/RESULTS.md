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
| base (E2, config v3, `m4-e2-dense-v3`) → GRPO dense | 1.6% [0.0, 4.0] | 4.0% [0.8, 8.0] | 0.0% | 50.4% [41.6, 59.2] | no change beyond noise (E2 v3 predictions) |
| primer-M + T8 (`m4-sft-primer-m-t8`) | 97.6% [94.4, 100.0] | 14.4% [8.8, 20.8] | 92.0% [87.2, 96.0] | 80.0% [72.8, 86.4] | P1 80–99% (point 93%), P2 20–75% (45%), P3 25–85% (55%), P4 85–100% (95%) (E3 predictions) |
| primer-M + T8 → GRPO dense (`m4-e3-dense`) | 97.6% [94.4, 100.0] | 7.2% [3.2, 12.0] | 91.2% [85.6, 96.0] | 80.0% [72.8, 86.4] | within ±10 points of the primer-M row on each task (E3 predictions) |
| primer-M + T8 → GRPO sparse (`m4-e3-sparse`, job `m4-e3-sparse-e0`) | 98.4% [96.0, 100.0] | 12.8% [7.2, 19.2] | 90.4% [84.8, 95.2] | 80.0% [72.8, 86.4] | not predicted (E0 on sparse added for M4's Done-when) |

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
| E2 base → GRPO dense, v3 | 24–30% (point 27%); see below | **25.8% [23.9, 27.8]** | 43.2% [41.7, 44.7] | 100.0% | **reference for E3 (H1)**; vs dense v2 −1.4 [−2.6, −0.1] | $9.99 with both evals (attempt 1 preempted after 4 min, $0.20) |
| E2 base → GRPO sparse, v3 | 22–29% (point 25.5%); see below | **28.0% [26.1, 30.0]** | 44.3% [42.7, 45.9] | 99.9% | +2.2 [+1.1, +3.4]; vs sparse v2 +4.5 [+3.0, +6.0] | $8.48 with test2000 |
| E3 primer-M (+ T8) only | 18–42% (point 30%) if the format holds; see below | **35.7% [33.6, 37.9]** | 55.8% [54.3, 57.4] | 100.0% | +9.9 [+8.2, +11.8] vs dense v3 | $22.01 SFT + evals (+ $4.16 stopped primer-M-only attempt) |
| E3 primer-M (+ T8) → GRPO sparse | 25–48% (point 37%) | **35.4% [33.4, 37.6]** | 56.0% [54.5, 57.5] | 99.8% | **+9.7 [+8.0, +11.3]**; vs primer only −0.2 [−1.6, +1.1]; vs primer → dense +2.9 [+1.8, +4.0] | $11.11 (3 preemptions, resumed from step 20) |
| E3 primer-M (+ T8) → GRPO dense | 26–50% (point 38%) | **32.6% [30.5, 34.7]** | 54.5% [53.1, 56.1] | 100.0% | **+6.8 [+5.2, +8.4]** (H1); vs primer only −3.1 [−4.5, −1.6] | $9.64 (preempted at step 140, resumed) |

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
reward and config tried (dense v1 23.8%, dense v2 27.2%, sparse v2 23.5%, dense v3 25.8%). dev500 reaches its
plateau by step ~25 (about $2) and stays at 21.6–29.0% from there to step 200. Neither more learning signal
(v2's entropy control) nor a denser reward lifted that plateau while the runs were healthy.
E0 didn't move either. That is the starting point H1 tests. The open problem for M4 is
the post-answer tail in config v2, which cost sparse its last 50 steps and pulled dense v2's
entropy controller off.

**E2 v3 predictions** (written 2026-10-23, before `m4-e2-dense-v3` launched; config v3 =
v2 + every rollout and eval stops at the first `</answer>`, ADR-022. The only v3 run so far is
the 4-step laptop smoke on Qwen3.5-0.8B, whose numbers mean nothing).
- **Dense v3 ≈ dense v2.** test2000 24–30% (point 27%), paired Δ vs dense v2 within ±3 points
  with a CI that includes 0. Removing the tail keeps the entropy controller on, but in v2 a
  steady supply of gradient (steps 31–90) didn't lift the dev plateau, so I don't expect v3 to.
  dev500 plateau 22–29% from step ~30 to 200, as in v1 and v2.
- **Sparse v3 tracks dense v3**, as sparse v2 did to step 150: test2000 22–29% (point 25.5%),
  paired Δ vs dense v3 −1.5 points (range −4 to +1), CI likely including 0.
- **Health, both arms:** our truncation share ≤ 1% on every step after step 10; prose before
  `<answer>` < 2% of completions at the end; mean completion ≤ 15 tokens after step 20; entropy
  coefficient > 0 on ≥ 70% of steps 30–200 (dense v2: it sat near 0 for steps 94–135 and from
  190); mean share of zero-spread groups over steps 50–200 ≤ 50% (dense v2: ~55–80% after
  step 94). Step time 30–45 s after step 20.
- **Cost:** $7–10 per run with both evals (dense v2 $9.22).
- **E0 on dense v3:** no change beyond noise from the base row.

**E2 v3 reading (dense, `m4-e2-dense-v3`).** test2000 25.8% [23.9, 27.8], inside the predicted
24–30%. Paired vs dense v2 it is −1.4 [−2.6, −0.1] (76 puzzles solved only by v3, 103 only by
v2). That is within the predicted ±3 points, but the CI just excludes 0 where I predicted it
would include it. With one seed per config I read this as "stopping at `</answer>` doesn't raise
the plateau", not as v3 being worse. Puzzle rating at 50% solve 973 [930, 1015] (v2 1011).
dev500 stayed at 23.2–29.0% from step 30 to 200 (predicted 22–29%). Health, as predicted:
truncation ≤ 0.6% on every step after step 10, prose before `<answer>` 0.03% over steps 180–200,
mean completion ≤ 14.9 tokens after step 20 (9.7 on average), entropy coefficient > 0 on 86% of
steps 30–200, median step 32 s (p90 42 s). One miss: zero-spread groups averaged 63% over steps
50–200 (predicted ≤ 50%). With the tail gone the controller stays on, but in most groups all
eight samples are still right or all wrong, so there is little signal for it to spread. E0
didn't move (P1 1.6%, P2 4.0%, P3 0%, P4 50.4%). Cost $9.99 for the attempt that ran, $10.19
with the preempted one: the top of the $7–10 range. Dense v3 is the E3 reference: the primer
arms run the same config and differ only in their start point.

**E2 v3 reading (sparse, `m4-e2-sparse-v3`).** test2000 **28.0% [26.1, 30.0]**, inside the
predicted 22–29% and above the point (25.5%). Paired vs dense v3 it is **+2.2 [+1.1, +3.4]** (94
puzzles solved only by sparse, 50 only by dense), where I predicted −1.5 (range −4 to +1). So
sparse v3 beat dense v3, and the miss is in sign as well as size. vs sparse v2: +4.5 [+3.0, +6.0];
v3 rescued the arm that v2's post-answer tail had wrecked. dev500 reached 22.8% by step 20 and
stayed at 24–29% to step 200 (27.6% at the end). Health as predicted: truncation ≤ 0.8% after
step 10, prose 0.02% over steps 180–200, mean completion ≤ 16.8 tokens after step 20, entropy
coefficient > 0 on 84% of steps 30–200, median step 32 s. As with dense v3, the zero-spread
share missed (80% over steps 50–200, predicted ≤ 50%). $8.48, inside $7–10. With both v3 arms
in, GRPO from the base lands at 26–28% whichever reward it uses: the plateau E2 found holds.

**E3 predictions** (written 2026-10-23, before the primer-M SFT launched; no primer-trained 2B
model exists yet. The only SFT run so far is the laptop wiring test on Qwen3.5-0.8B, with 256
examples and two trainable layers, whose numbers mean nothing.) Primer-M T5 holds 390k "Best
move?" examples. About half are solver positions of `primer_pool` puzzles, answered with the
puzzle solution; the rest are eval-DB positions, answered with Stockfish's best move. So the
primer is supervised move imitation as well as rules teaching.
- **Format first.** The primer answers bare (`Qxc8+`), and the RL prompt asks for `<answer>`
  tags. I give 65% to the primer checkpoint keeping a dev500 format rate ≥ 50% (point 75%).
  **Pre-registered stop rule:** if the SFT probe's format rate (32 dev500 RL prompts) is below 50%
  at two checkpoints in a row, I stop the VM and bring the T8 fallback (TRAINING.md §5) to the
  user. At the end, the task's rule applies: dev500 format < 50% → T8.
- **Primer-M only (test2000), if the format holds:** solve 18–42% (point 30%), move accuracy
  40–58%, legal ≥ 95%, puzzle rating ~1050–1300. That's about E2 dense v3's level from imitation
  alone. The gain over base is largest in the 800–1799 bins.
- **E0 on primer-M:** P1 square 80–99% (point 93%), P2 legal count 20–75% (45%; exact counting
  without search is hard), P3 FEN after a move 25–85% (55%), P4 in check 85–100% (95%). In
  every case well above the base row, which copies the hint. Part of that gain is format
  (see the E0 note).
- **Primer → GRPO dense (H1):** test2000 26–50% (point 38%). Paired Δ vs E2 dense v3 about +11
  points (range +2 to +20). I give H1 (Δ ≥ 3 with a CI that excludes 0) 75%.
- **Primer → GRPO sparse (H2):** 25–48% (point 37%), about 1 point below primer → dense. I give
  H2 85%: sparse gains ≥ 3 points over the primer-only start, since base → sparse learned too.
- **H5 (RL adds to the primer):** primer → dense − primer only ≈ +8 points (range 0 to +16). 70% on
  ≥ 3 points with a CI that excludes 0.
- **pass@k on dev500 (T = 1, n = 8):** RL sharpens more than it discovers (Shen et al.). pass@1
  rises from primer to primer → GRPO, and pass@8 moves less (within ±5 points).
- **Health of the primer arms under v3:** completions stay short (mean ≤ 15 tokens), prose before
  `<answer>` < 2%, truncation ≤ 1%.
- **Cost:** SFT job 4.5–7 h, $15–23 (point $19); each primer → GRPO arm $7–10.

**E3 primer SFT, attempt with primer-M alone (`m4-sft-primer-m`, stopped).** The format broke as
feared: the probe scored format 1.00 at step 0 and **0.00** at the first checkpoint (step 53),
answering with bare moves (`Qxh2#`). Loss 0.83 → 0.56 and answer-token accuracy 71% → 80% from
step 25 to step 75. The rule above said stop after two failed checkpoints. The user asked for
anything that speeds M4 up, so it stopped after one, at ~step 95 ($4.16). The T8 fallback
(ADR-024) follows: primer-M plus 26k RL-format copies of T5 examples, answered
`<answer>SAN</answer>`, with no think block.

**T8 predictions** (written 2026-10-23, before `m4-sft-primer-m-t8`'s first checkpoint; no
model has trained on T8 yet). The E3 predictions above stand for the primer-M + T8 model, as the
"if the format holds" case.
- **Format:** probe format ≥ 50% at the first checkpoint, 85%; ≥ 90% there, 65%. Final dev500
  format ≥ 95%, 80%. 2% is ~35 examples per optimizer step, each with the instruction line that
  tells the two formats apart.
- **Primer content:** T8 repeats moves T5 already teaches, so loss and answer accuracy on the
  other tasks track the stopped run to within noise at matching steps (e.g. ~0.56 / ~80% near
  step 75).

**E3 primer-only reading (`m4-sft-primer-m-t8`, 768 steps, 7.03 h, $22.01).** T8 held the format
at every checkpoint (probe format 1.00 at steps 54 to 601), and the final model's dev500 format
is 100.0%, legal 100.0%, ~9 tokens per answer: the T8 predictions came true (≥ 50% at the first
checkpoint, 85%; ≥ 90%, 65%; final ≥ 95%, 80%). Training loss 0.86 → 0.28, answer-token accuracy
70% → 90%, matching the stopped run where they overlap. **test2000 solve 35.7% [33.6, 37.9]**,
move accuracy 55.8%, puzzle rating at 50% solve 1237 [1195, 1278] (dense v3: 973). That's inside
the predicted 18–42% (point 30%) and above it at the point, with move accuracy inside 40–58% and
the rating inside 1050–1300. **Imitation alone beats RL from the base model by +9.9 points**
paired [+8.2, +11.8] (275 puzzles solved only by the primer model, 77 only by dense v3), at about
twice the cost ($22 vs $10). The gain is spread over every bin from 600 to 1999 (e.g. 1000–1199:
57.5% vs 34.1%; 1400–1599: 29.3% vs 18.0%). dev500 solve 35.2% [31.0, 39.6]. pass@k on dev500
(n = 8, T = 1): primer @1 28.1%, @4 43.4%, @8 51.4%; base @1 1.2%, @8 6.0%. E0: P1 97.6%, P2
14.4%, P3 92.0%, P4 80.0% (predicted P1 80–99%, P2 20–75%, P3 25–85%, P4 85–100%): P1 and P3
beat or meet the predictions, legal-move counting (P2) is below them although the full legal
list scores F1 73.2%, and P4 is under the 85% floor. The task's E0 gate (P3 not near 0) passes,
so the GRPO arms go ahead.

**E3 primer → GRPO dense reading (`m4-e3-dense`).** test2000 **32.6% [30.5, 34.7]**, move
accuracy 54.5%, rating at 50% solve 1151 [1107, 1194]. Paired vs E2 dense v3: **+6.8 [+5.2,
+8.4]** (202 puzzles solved only by this arm, 66 only by dense v3), so **H1 holds** (Δ ≥ 3 with a
CI that excludes 0; predicted +11, range +2 to +20, 75%). But GRPO **lowered** the primer
model's own score: −3.1 [−4.5, −1.6] paired vs primer only (81 vs 143 puzzles). **H5 fails** (I
gave ≥ +3 70%). The H1 gain is the primer's, not RL's on top of it. Dev500 shows the path: 35.4%
at step 0, 36.8% at step 20, a dip to 28.0% at step 50 and 28.0% at step 120, then 36.2% at step
200. Test2000 is graded on the final model only. pass@k on dev500 (T = 1, n = 8) fell on every
k: @1 28.1 → 26.6%, @4 43.4 → 37.6%, @8 51.4 → 42.8%. RL narrowed the sample distribution
without lifting greedy accuracy, as predicted for pass@8, but pass@1 didn't rise either.

A likely cause, not tested: config v3's entropy floor. The adaptive bonus (ADR-021) targets
token entropy 0.2, set from the base model's runs. The primer model starts at 0.11, so the
controller raised the coefficient to ~0.64 by steps 21–60 (dense v3: 0.12–0.18) and pushed the
policy away from its sharp primer answers. That is where dev500 dropped. Zero-spread groups
averaged ~30% (dense v3: 63%), so the arm had plenty of gradient. KL to the start rose to ~0.25
over steps 121–200. Health otherwise as predicted: format 100%, truncation 0, prose ~0, ~8.5
tokens per answer. E0 stayed within ±10 points of the primer row on every task (P2 legal count
14.4 → 7.2%). The arm was preempted at step 140 (us-central1-c) and resumed from its step-140
checkpoint in europe-west4-a; dev500 was continuous across the restart (31.4% → 32.8%).

**E3 primer → GRPO sparse reading (`m4-e3-sparse`).** test2000 **35.4% [33.4, 37.6]**, move
accuracy 56.0%, legal 99.8%, rating at 50% solve 1237 [1199, 1276]. That's inside the predicted
25–48% (point 37%). Paired vs E2 dense v3: +9.7 [+8.0, +11.3]. Paired vs primer only: **−0.2
[−1.6, +1.1]** (91 vs 96 puzzles), so sparse GRPO left the primer model where it was. **H2 is
falsified** as RESEARCH.md §3 states it ("sparse reward on the primer model stays within noise of
its start"). I gave its pre-registered form (≥ 3 points over primer only) 85%. Sparse beat dense
from the same start by +2.9 [+1.8, +4.0], where I predicted dense 1 point ahead. The dev500 path
matches dense's, only shallower: 35.4% at step 0, 36.2% at step 30, a dip to 31.6% at step 50
(dense: 28.0%), back to 36.2% at step 200. The entropy coefficient again climbed (0.58 over steps
21–60; dense 0.64) toward the 0.2 target from 0.13–0.15. Zero-spread groups averaged 51% over
steps 50–200 (dense 30%): with a binary reward more groups agree, so the bonus moves the policy
less. pass@k on dev500 fell from primer only's @1 28.1 / @4 43.4 / @8 51.4% to 28.4 / 40.5 / 47.0%:
pass@1 unchanged, pass@8 down 4.4 points. Health: format 100%, truncation 0, ~8.5 tokens per
answer, prose ~0.1%. The run was preempted three times in us-central1-c (at steps ~0, ~35 and
~20 after resuming) and finished from its step-20 checkpoint in europe-west4-a. Its cost was
$11.11, $2.68 of it in the three short attempts.

**pass@k on dev500** (8 samples at T = 1; greedy solve in the last column):

| Model | pass@1 | pass@4 | pass@8 | greedy |
|---|---|---|---|---|
| base (Qwen3.5-2B) | 1.2% | 3.9% | 6.0% | 5.2% |
| primer-M + T8 | 28.1% | 43.4% | 51.4% | 35.2% |
| primer → GRPO dense | 26.6% | 37.6% | 42.8% | 36.2% |
| primer → GRPO sparse | 28.4% | 40.5% | 47.0% | 36.2% |
| primer → GRPO dense, entropy target 0.14 (ADR-025) | 28.0% | 39.3% | 45.0% | 36.4% |

GRPO on the primer model kept or slightly lowered pass@1 and cut pass@8 by 4–9 points. That is
sharpening without discovery (Shen et al.), and here the sharpening doesn't reach greedy accuracy
either. Greedy dev500 rose by 1 point for both arms, while test2000 didn't move or fell.

**H5 across all three primer → GRPO runs:** none added to the primer (dense −3.1, sparse −0.2, dense with the matched entropy target −0.9, paired vs
primer only). The primer's gain over GRPO-from-base (+9.9) is SFT on teacher-free data. RL with
these rewards, this config and 200 steps either kept it (sparse) or cost a little of it (dense).

**Entropy-target ablation predictions** (written 2026-10-24, before `m4-e3-dense-ent014`
launched; ADR-025: `m4-e3-dense` with `entropy_target` 0.14 instead of 0.2).
- **The dev dip goes away:** no dev500 eval more than 4 points below step 0 (35.4%), 70%. The bonus
  coefficient stays below 0.2 on average over steps 21–60, 80%. In `m4-e3-dense` it averaged 0.64.
- **test2000:** 33–38% (point 35.5%). Paired vs primer only: −2 to +2.5 (point 0). H5's bar (≥ 3
  with a CI that excludes 0) is met with only 15%. Paired vs `m4-e3-dense`: positive, 75%.
- **pass@8 on dev500:** above `m4-e3-dense`'s 42.8%, 70%, and below primer only's 51.4%, 75%.
- **Health:** format ≥ 99%, truncation ≤ 1%, mean completion ≤ 15 tokens; zero-spread groups
  averaging 30–50% (lower entropy, so more groups agree than in `m4-e3-dense`'s ~30%).
- **Cost:** $7–10.

**Entropy-target ablation reading (`m4-e3-dense-ent014`, ADR-025).** test2000 **34.8% [32.6,
36.9]**, move accuracy 55.6%, rating at 50% solve 1214 [1173, 1254]. Paired vs primer only: **−0.9
[−2.3, +0.4]**, within noise. vs `m4-e3-dense` (target 0.2): +2.1 [+1.1, +3.2]. vs E2 dense v3:
+8.9 [+7.3, +10.5]. So the base-tuned entropy floor explains `m4-e3-dense`'s loss. With the
target at the primer's own entropy, GRPO keeps the primer's score, but it still doesn't add to
it. Checked against the predictions:
- dev500 stayed within 4 points of step 0: its low was 32.0% at step 50, against 28.0% for target
  0.2. It ended at 36.4%. ✓
- The bonus coefficient stayed below 0.2 over steps 21–60: **✗**, it averaged 0.59 (target 0.2
  run: 0.64). Entropy fell below 0.14 by itself (0.106 over steps 1–20), so the controller ramped
  up anyway. What the lower target changed is where it stopped: entropy averaged 0.109 over
  steps 21–60 (target 0.2: 0.177) and 0.148 over steps 61–200 (0.208). KL to the start averaged
  0.114 over steps 121–200, versus 0.253.
- test2000 inside 33–38% ✓; paired vs primer only inside −2 to +2.5 ✓; H5's bar not met (I gave it
  15%) ✓; above `m4-e3-dense` ✓.
- pass@k on dev500: @1 28.0%, @4 39.3%, @8 45.0%. pass@8 is above `m4-e3-dense` (42.8%) ✓ and below
  primer only (51.4%) ✓.
- Health: format 100%, truncation 0, ~8.5 tokens per answer, zero-spread groups 36% over steps
  50–200 (predicted 30–50%) ✓. Training legal rate at T = 1 was 0.988 over steps 180–200 (target
  0.2 run: 0.977).
- Cost $10.21, just over the predicted $7–10. Four preemptions in us-central1-c cost $5.74 in
  attempts that were cut short; the run resumed from steps 20, 30, 30 and 100.

Figures (E2): dev500 solve rate vs dollars spent for all three runs
(`results/figures/e2_dev_vs_usd.png`), and training metrics per step: move-match rate, legal and
format rates, length, truncated share, prose share, entropy, dead groups and KL
(`results/figures/e2_components.png`). M4 adds the E3 arms and a per-bin figure
(`results/figures/e3_bins.png`).

## E4: primer scaling (test2000, GRPO dense)

Each primer row has two numbers: the primer-only SFT model and primer → GRPO dense (ADR-026 §2).
The M row's GRPO number is the ≈ v4 arm (`m4-e3-dense-ent014`, ADR-027).

| Primer | Tokens | Predicted (SFT only / → GRPO) | SFT only | → GRPO dense | Run $ |
|---|---|---|---|---|---|
| none (E2) | 0 | — | base 4.1% | 25.8% [23.9, 27.8] (dense v3 = v4) | $9.99 |
| S + T8 | 19.2M | 12–28% (point 20%) / 24–34% (point 29%) | | | |
| M + T8 (E3) | 192.5M | done | 35.7% [33.6, 37.9] | 34.8% [32.6, 36.9] | $22.01 + $10.21 |
| L | ~450M | ⏭️ dropped in the M3 re-plan (new data + the most expensive SFT) | | | |

**E4 predictions** (written 2026-10-25, before `m5-sft-primer-s-t8` launched and before any E5a
result). Primer-S + T8 is 132,489 examples: the first 130k of primer-M, plus the 2,489 T8
examples drawn from them (ADR-028). That is ~77 optimizer steps of the same recipe.
- **Format:** T8 is 1.88% of S (M-t8: 1.96%), ~32 examples per step. Probe format ≥ 50% at the
  first checkpoint: 80%. Final dev500 format ≥ 95%: 75%.
- **Primer-S only (test2000):** solve 12–28% (point 20%), move accuracy 30–48%, legal ≥ 97%. A
  tenth of the imitation data (19k puzzle solutions instead of 195k) buys well under a tenth of
  the gain, because the easy bins saturate first.
- **E0 on primer-S:** P1 60–95% (point 80%), P2 3–15% (8%), P3 20–70% (45%), P4 60–85% (75%).
- **v4's entropy start:** between the base (0.83) and primer-M (0.14). Above 0.2, so v4 runs as v3:
  55%.
- **Primer-S → GRPO dense:** 24–34% (point 29%). Unlike primer-M, a weaker start leaves RL
  room, so **H5 for S** (RL adds ≥ 3 with a CI that excludes 0, paired vs primer-S only): 65%.
- **H3** (post-RL solve rises with primer size): none 25.8% < S < M 34.8%, each step a paired Δ
  with a CI that excludes 0: 55%. With three points, "roughly log-linear" can't be tested
  beyond monotonicity. I'll report it as such.
- **Cost:** SFT job 1–1.5 h, $3–5. GRPO $8–12.

## E5: ablations

| ID | Arm | Predicted | Result | Run $ | Status |
|---|---|---|---|---|---|
| E5a | rules-only primer (SFT only) | 3–12% (point 6%) if the format holds | | | |
| E5a | rules-only primer → GRPO dense (v4) | 24–33% (point 28%); Δ vs E2 dense v3 +2 (−2 to +7) | | | |
| E5b | no legal-move list | | | | |
| E5c | ~4B model, best recipe | | | | ⏭️ doesn't fit the M5 line (user's choice at the M5 start: E5a, E4, E5b, E5d) |
| E5d | LoRA r=8 vs r=64 | | | | |
| M4 ablation (ADR-025) | primer → GRPO dense, entropy target 0.14 instead of 0.2 | 33–38% (point 35.5%); Δ vs primer only −2 to +2.5 | **34.8% [32.6, 36.9]**; vs primer only −0.9 [−2.3, +0.4]; vs `m4-e3-dense` +2.1 [+1.1, +3.2] | $10.21 (4 preemptions) | done |

**M5 plan** (agreed with the user on 2026-10-25): E5a, E4, E5b, E5d in that order, within the
$110 M5 line (~$75 planned). E5c is skipped. Every GRPO arm runs config v4 (ADR-027: the entropy
target is min(0.2, the mean of steps 1–5)). For the base start, v4 is the same as v3. For
primer-M it is ≈ the ent014 ablation, which is therefore the "primer-M → GRPO dense" reference
for M5.

**E5a predictions** (written 2026-10-25, before `m5-sft-rules-m` launched; no model has trained
on rules-M yet). Rules-M (ADR-028) is T1–T4 only: 1,455,000 examples, as many tokens as primer-M,
with about twice its answer tokens. No answer is a move choice, no prompt shows the legal-move
line, and no example uses `<answer>` tags.
- **Format.** Without T5 there is no bare-move habit on a near-identical prompt, which is what
  broke primer-M's format. But 1.46M bare answers to FEN questions could still teach the model to
  answer the RL prompt bare, or with a move list. Probe format ≥ 50% at the first checkpoint: 70%.
  Final dev500 format ≥ 90%: 60%. **Pre-registered stop rule**, as in E3: if the probe format is
  below 50% at two checkpoints in a row, I stop the VM and ask the user. A T8-style fix would
  have to carry no move choice (ADR-028).
- **Rules-only SFT on its own (test2000), if the format holds:** solve 3–12% (point 6%), move
  accuracy 15–28%, legal ≥ 97%. Knowing the captures and checks may raise the base model's move
  choice a little, but nothing in rules-M says which move wins.
- **E0:** P1 square 90–99% (point 97%), P2 legal count 10–40% (20%), P3 FEN after a move 85–97%
  (92%), P4 in check 75–95% (85%). That is primer-M's level or above, since rules-M has 2.2×
  primer-M's T1–T4 examples.
- **v4's entropy start:** above 0.2, so the target stays 0.2 and the arm runs as v3: 70%.
- **Rules → GRPO dense (H4):** test2000 24–33% (point 28%), paired vs E2 dense v3 (25.8%) +2
  (range −2 to +7). H4 asks for at least half of the full primer's post-RL gain. Against
  primer-M → GRPO dense at the ≈ v4 target (ent014, 34.8%, +9.0 paired over E2 dense v3), the bar
  is ≥ 30.3%. I give that 25%. "Rules-only ≈ no primer" (Δ < 3 or a CI that includes 0): 55%.
- **pass@8 on dev500:** rules-only SFT 5–15% (base 6.0%). After GRPO 30–42%, a few points above
  its greedy dev500 score, as for the primer arms (greedy 36%, pass@8 43–47%).
- **Health after GRPO:** format ≥ 99%, ~9 tokens per answer, truncation ≤ 1%.
- **Cost:** SFT 6.5–8 h, $20–26 (point $22). GRPO $8–12.

**E5a SFT, attempt on rules-M alone (`m5-sft-rules-m`, stopped).** The format broke here too.
The probe scored format 1.00 at step 0 and **0.00** at the first checkpoint (step 59), with no
`<answer>` tag in any answer: bare moves (`Qxb4`, `Qxa4`, often the base model's own step-0
picks). The prediction (≥ 50% at the first checkpoint, 70%) failed. So the T5 prompt wasn't
needed to break the format: 1.46M bare answers to FEN questions did it. Training itself looked
like primer-M's: 27.3 s per step, 8.1k tok/s, loss 0.38 and answer-token accuracy 86.6% at step
59 (of 843). The user stopped it after one checkpoint (0.82 h, $2.58). The T9 fallback (ADR-029)
follows: 2% copies of rules-M items asked in the RL prompt's layout and answered in `<answer>`
tags. None of them answers with a move choice.

**T9 predictions** (written 2026-10-25, before `m5-sft-rules-m-t9` launched; no model has
trained on T9 yet). The E5a predictions above stand for the rules-M + T9 model, as the "if the
format holds" case.
- **Format:** probe format ≥ 50% at the first checkpoint: 65%; ≥ 90% there: 45%. Final dev500
  format ≥ 90%: 55%. T8 matched the RL prompt's instruction and answer type exactly. T9 matches the
  layout and the answer-tag sentence but not the answer type, so the habit has to carry over from
  "the answer" to "one move". **Stop rule:** probe format < 50% at the first checkpoint → stop
  and ask (ADR-029).
- **If the format holds only partly** (50–90% on dev500), the SFT-only number understates the
  model by the format losses. I'll report it as graded, with the parse-failure share next to it.

**T9 at 2% reading (`m5-sft-rules-m-t9`, stopped).** Probe format 1.00 at step 0 and **0.375**
at the first checkpoint (step 54). All 12 tagged answers were legal. The untagged ones were bare
moves (`Qxg2#`, `Qh8+`). That is below the predicted ≥ 50% (65%) but well above rules-M alone
(0.00). ADR-029's rule stopped it (0.77 h, $2.41). The step-54 checkpoint never finished
copying, so the next run starts over. The user chose T9 at 10% with no third stop (ADR-030).

**T9 at 10% predictions** (written 2026-10-25, before `m5-sft-rules-m-t9-10` launched). 145,500 T9
copies, ~170 per optimizer step instead of ~35.
- **Format:** probe format ≥ 50% at the first checkpoint: 80%; ≥ 90% there: 55%. Final dev500
  format ≥ 90%: 60%; ≥ 50%: 85%.
- **Rules content:** loss and answer-token accuracy on T1–T4 track `m5-sft-rules-m` where they
  overlap (~0.38 and ~87% near step 59). The T9 copies repeat answers rules-M already has.
- **The E5a predictions above stand** for this model, if the format holds. If it ends below 90%,
  the SFT-only solve rate understates it by about the untagged share, and the GRPO arm starts by
  learning the tags (ADR-030).
- **Cost:** ~8 h, $24–28.

**E5b predictions** (written 2026-10-25, before any E5b run and before any E5a or E4 result).
The arm is primer-M + T8 → GRPO dense under v4 with the prompt's legal-move line dropped. The same
job evaluates the primer-only model and the base model on test2000 without the list. With-list
references: base 4.1% (legal 96.4%), primer-M + T8 only 35.7%, primer → GRPO dense ≈ v4 (ent014)
34.8%.
- **Base without the list:** solve 1–4% (point 2.5%), legal 55–90% (point 75%). The list was its
  main source of legal moves.
- **Primer-M + T8 only, without the list:** format ≥ 90%: 65%. T8 taught the tags under the
  with-list instruction only, and the no-list instruction words it differently ("exactly one
  legal move"). Solve 22–34% (point 29%), legal 90–99% (T2 taught legal moves; E0's legal-list F1
  is 73%).
- **Primer → GRPO dense without the list:** test2000 28–36% (point 32%). Paired vs ent014 (with
  the list): −3 (range −7 to +1). "The primer replaces the crutch" (|Δ| < 3 with a CI that
  includes 0): 45%. Legal ≥ 98% after GRPO: 80%.
- **Cost:** $10–14 (the two extra test2000 evals add ~$0.3).

**E5d predictions** (written 2026-10-25, before either E5d run). Base → GRPO dense, v4 (= v3 for
the base start), LoRA rank 8 and 64 against rank 32 (`m4-e2-dense-v3`: dev500 5.2% at step 0,
24.0% at step 20, 26.4% at step 100), 100 steps, the same seed, data order and schedule.
- **Step 100 on dev500:** all three ranks within ±3 points of each other: 70% (LoRA Without
  Regret: RL moves few bits, so low rank is enough). Point predictions: r=8 25.5%, r=64 26.5%.
- **Speed:** r=8 reaches 20% on dev500 no later than r=32 + 10 steps: 75%. Seconds per step within
  ±10% of r=32: 80%.
- **Cost:** $4–6 per run.

## Hypothesis verdicts

| | Verdict | Evidence |
|---|---|---|
| H1 | **holds** | Primer → GRPO beats GRPO from the base on test2000 under both rewards: dense +6.8 [+5.2, +8.4] vs E2 dense v3, sparse +7.4 [+5.8, +9.2] vs E2 sparse v3 (one seed per arm). The gain is the primer's: primer only is +9.9 [+8.2, +11.8] vs E2 dense v3. |
| H2 | **falsified as stated** | Sparse reward on the primer model stays within noise of its start: −0.2 [−1.6, +1.1] vs primer only. Sparse reward does learn from the *base* model under v3 (4.1% → 28.0%), unlike Chess-R1's 3B, so the "sparse can't learn" premise fails here for the base, not the primer. |
| H3 | | |
| H4 | | |
| H5 | **fails** | Primer only ≈ primer → GRPO for all three RL runs: dense −3.1 [−4.5, −1.6], sparse −0.2 [−1.6, +1.1], dense with the entropy target at the primer's own entropy −0.9 [−2.3, +0.4] (ADR-025). The dense arm's loss was the base-tuned entropy floor; without it RL keeps the primer's score but adds nothing, and pass@8 falls (51.4% → 42.8–47.0%). |

## Cost summary

| Pool | Ceiling | Spent | Biggest line items |
|---|---|---|---|
| compute | 360 | $131.02 (to M4) | M4 $75.92: SFT primer-M + T8 $22.01 (+ $4.16 stopped primer-M-only run), E3 dense $9.64, E3 sparse $11.11, entropy ablation $10.21, E2 dense v3 $10.19, E2 sparse v3 $8.48, E0 sparse $0.11; M3 $50.15 |
| vertex | 180 | $0 | none; the Premium Support credit was drawn for Compute Engine instead (BUDGET §1, 2026-10-24) |
