# Results

Write **predictions before running** each experiment (CLAUDE.md), in the
"Predicted" column, committed before the launch. Measured values carry 95%
bootstrap CIs. Arm-vs-arm differences use a paired bootstrap. Model: _(set
in M2)_.

## E0: knowledge probe (probe500, exact match %)

| Checkpoint | P1 square | P2 legal count | P3 FEN after move | P4 in check | Predicted |
|---|---|---|---|---|---|
| base (zero-shot) | | | | | P1 40–60%, P2 2–8%, P3 0–2%, P4 55–75% (written 2026-10-21, before any run) |
| primer-M | | | | | |
| primer-M → GRPO dense | | | | | |

## E1: baselines (test2000 unless noted)

Predictions written 2026-10-21, before any test2000 run. Two harness smoke
tests had been run on dev500 by then: random on all 500 (1.0% solved) and
Stockfish 1k nodes on 100 puzzles (87%).

| Model | Predicted solve | Solve rate | Move acc | Legal rate | Puzzle rating | $ / 1k puzzles |
|---|---|---|---|---|---|---|
| random legal | ~1% | | | 100% | | 0 |
| Stockfish 1 node | 30–45% (rating ~1000–1300) | | | 100% | | 0 |
| Stockfish 1k nodes | 85–92% (rating > 2400) | | | 100% | | 0 |
| base model (zero-shot) | 2–8%, legal 60–90%, rating below range | | | | | |
| Gemini Flash-Lite | 5–15% | | | | | |
| Gemini Flash | 15–35% | | | | | |
| Gemini Pro (test500) | 30–55% | | | | | |
| Chess-R1, Qwen2.5-7B dense (reported, different set) | | | ~25–30% | | | — |

## E2 / E3: the main comparison (test2000)

| Arm | Predicted solve | Solve rate | Move acc | Legal | Δ vs E2-dense (paired) | Run $ |
|---|---|---|---|---|---|---|
| E2 base → GRPO sparse | | | | | | |
| E2 base → GRPO dense | | | | | — | |
| E3 primer-M only | | | | | | |
| E3 primer-M → GRPO sparse | | | | | | |
| E3 primer-M → GRPO dense | | | | | | |

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
