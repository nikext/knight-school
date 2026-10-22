# qwen3.5-2b on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`
- git `90bfc56fc862`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T08:22:10Z, 105 s, cost $0.0536 ($0.541/h)
- **rescored** 2026-10-22T08:26:49Z at git `f853bceeea25`: format no longer requires a think block in the completion when the chat template pre-fills one (ADR-017)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 4.1% [3.2, 5.0] |
| move accuracy | 15.6% [14.6, 16.6] |
| legal rate | 96.4% [95.8, 97.0] |
| format rate | 100.0% [99.9, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 10 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0268 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 10.8% |
| 600-799 | 167 | 15.6% |
| 800-999 | 167 | 7.8% |
| 1000-1199 | 167 | 7.2% |
| 1200-1399 | 167 | 3.0% |
| 1400-1599 | 167 | 1.8% |
| 1600-1799 | 167 | 1.8% |
| 1800-1999 | 167 | 0.0% |
| 2000-2199 | 166 | 0.0% |
| 2200-2399 | 166 | 0.0% |
| 2400-2599 | 166 | 0.6% |
| 2600-2799 | 166 | 0.6% |

## Examples

**W71jq-1** (rating 402), solution `Qe1+`, answer `Qe1+` (ok, right)

````text
<answer>Qe1+</answer>
````

**6rBVg-1** (rating 1635), solution `hxg4`, answer `hxg4` (ok, right)

````text
<answer>hxg4</answer>
````

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qf4+` (ok, wrong)

````text
<answer>Qf4+</answer>
````

**SIOAW-5** (rating 1860), solution `Kxc3`, answer `Kc5` (ok, wrong)

````text
<answer>Kc5</answer>
````

**pOu5j-1** (rating 532), solution `Rg1+`, answer `-` (illegal, wrong)

````text
<answer>Qd4</answer>
````
