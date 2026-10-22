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
| E2 base → GRPO dense, v2 | 22–33% (point 28%); see below | | | | (reference for v2 arms) | |
| E2 base → GRPO sparse, v2 | 16–30% (point 24%); see below | | | | | |
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
- **Dense v2** keeps learning after step 25 instead of flattening: dev500 at step 50 about 21%
  (it may start a little slower than v1), and test2000 22–33% (point 28%), about +4 points over
  v1 (paired). The gain over v1 is mostly in the 800–1599 bins. Completions stay short (mean
  ≤ 20 tokens). I'd put 25% on prose before `<answer>` reaching > 10% of completions by the end.
- **Sparse v2** learns, behind dense: 16–30% (point 24%), paired Δ vs dense v2 about −4 points,
  with a CI that may include 0. This drops the original "sparse ≈ flat, replicates Chess-R1"
  expectation (RESEARCH.md E2) on the strength of v1's first 19 steps.

Figures: dev solve rate vs $ spent, all arms overlaid
(`results/figures/e2e3_curves.png`), and per-bin solve rate
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
