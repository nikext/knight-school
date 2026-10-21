# Knight School

Teaching a small open LLM chess tactics with reinforcement learning, on a
fixed cloud budget, with every dollar logged.

> **Status: M0 done (money guardrails, launcher, kill switch).** The code is
> built milestone by milestone, one fresh Claude Code session per milestone.
> See [docs/PLAN.md](docs/PLAN.md) for where things stand.

## The question

[Chess-R1](https://arxiv.org/abs/2507.00726) (KAIST & KRAFTON, 2025) trained
3–8B LLMs with GRPO on Lichess puzzles. Every model plateaued at roughly
25–30% puzzle accuracy, far below an 1800-rated player (66.5%). With a sparse
"right move or not" reward, the 3B model did not learn at all. The authors'
diagnosis was that the base models lack chess knowledge (0% on a board-state
probe), and RL cannot add knowledge that isn't there.
[Shen et al. (2026)](https://www.alphaxiv.org/abs/2607.16097) reached the same
conclusion from the other side. In models pretrained from scratch on chess
games, pretraining quality predicts where RL ends up.

Knight School tests the obvious follow-up on an off-the-shelf small model:

> **Does a cheap, teacher-free "chess primer", meaning supervised fine-tuning on
> board reading, rules and Stockfish-annotated positions built entirely from
> CC0 Lichess data, raise the RL ceiling? How does the ceiling scale with
> primer size, and is it the rules or the Stockfish moves that matter?**

No LLM-written reasoning traces are used anywhere. Every training signal comes
from python-chess (rules) or Stockfish (move quality).

## Experiments

| | What | Milestone |
|---|---|---|
| E0 | Diagnostics: board-state and legal-move probes, for every model and stage | M2 onwards |
| E1 | Baselines: zero-shot open models, Gemini, random legal move, weak Stockfish | M2 |
| E2 | GRPO on the base model, sparse vs dense (Stockfish) reward | M3 |
| E3 | Primer SFT → GRPO, sparse vs dense, plus a primer-only control | M4 |
| E4 | Primer size scaling (S / M / L) → RL ceiling | M5 |
| E5 | Ablations: rules-only primer, no legal-move list, ~4B model | M5 |

Headline metric: solve rate on 2,000 held-out Lichess puzzles stratified by
rating, with 95% bootstrap confidence intervals. Results go in
[docs/RESULTS.md](docs/RESULTS.md), negative ones included. Predictions are
written down before each experiment runs.

## Budget

| Pool | Credit (left on 2026-10-21) | Ceiling this project plans to | Spent |
|---|---|---|---|
| GCP compute | $440.94, expires 2026-11-12 | $360 | see `make costs` |
| Vertex AI (Gemini baselines) | $209.26, expires 2027-04-08 | $180 | see `make costs` |

GPUs are spot only, one GPU at a time (the quota is set to 1), every job has a
hard time limit, and a launcher refuses any job whose worst-case cost would
break the ceiling, or that could still be running when its credit expires. Budgets and a kill switch act as the backstop. The full
rules are in [docs/BUDGET.md](docs/BUDGET.md), and the ledger is
[costs/ledger.jsonl](costs/ledger.jsonl).

## Running a build session

```bash
cd ~/Documents/GitHub/knight-school
claude
> Do the next milestone in docs/PLAN.md.
```

The session reads [CLAUDE.md](CLAUDE.md), finds the next milestone in the
status table, and works from its task file in [docs/tasks/](docs/tasks/).

## Docs

| File | What's in it |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | Status table and milestone summaries |
| [docs/tasks/](docs/tasks/) | One self-contained task file per milestone |
| [docs/BUDGET.md](docs/BUDGET.md) | Money rules, allocations, guardrails, ledger |
| [docs/RESEARCH.md](docs/RESEARCH.md) | Question, prior work, hypotheses, experiment design |
| [docs/DATA.md](docs/DATA.md) | Lichess data, splits, Stockfish rewards, primer tasks |
| [docs/TRAINING.md](docs/TRAINING.md) | Models, SFT and GRPO setup, checkpoints |
| [docs/EVALS.md](docs/EVALS.md) | Eval sets, metrics, harness, baselines |
| [docs/GCP.md](docs/GCP.md) | Project, quotas, launch backends, kill switch, teardown |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADRs |
| [docs/RESULTS.md](docs/RESULTS.md) | Predictions and measured results |

## License

Code: Apache-2.0. Lichess puzzle and evaluation databases: CC0. Stockfish is
GPL-3.0; it is used as a tool and is not redistributed.
