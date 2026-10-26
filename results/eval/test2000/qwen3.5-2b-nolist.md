# qwen3.5-2b-nolist on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b-nolist`
- git `7190e0411a2e`, prompt hash `49f43a62cf0a`, legal list off
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T11:45:33Z, 16 s, cost $0.2206 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 0.1% [0.0, 0.1] |
| move accuracy | 0.2% [0.1, 0.4] |
| legal rate | 8.9% [7.9, 9.9] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 9 / 9 |
| prompt tokens mean | 115 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1103 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 0.0% |
| 600-799 | 167 | 0.0% |
| 800-999 | 167 | 0.6% |
| 1000-1199 | 167 | 0.0% |
| 1200-1399 | 167 | 0.0% |
| 1400-1599 | 167 | 0.0% |
| 1600-1799 | 167 | 0.0% |
| 1800-1999 | 167 | 0.0% |
| 2000-2199 | 166 | 0.0% |
| 2200-2399 | 166 | 0.0% |
| 2400-2599 | 166 | 0.0% |
| 2600-2799 | 166 | 0.0% |

## Examples

**BgzUj-1** (rating 489), solution `Qc8+`, answer `Qc8+` (ok, right)

````text
<answer>Qc8</answer>
````

**i4jiN-1** (rating 1787), solution `Qf6+`, answer `Qf6+` (ok, right)

````text
<answer>Qf6</answer>
````

**0Y3oP-1** (rating 526), solution `Qxg2#`, answer `Qc8` (ok, wrong)

````text
<answer>Qc8</answer>
````

**7aAUo-7** (rating 1798), solution `Qh2#`, answer `Qc8` (ok, wrong)

````text
<answer>Qc8</answer>
````

**2IOMH-1** (rating 496), solution `Qe1#`, answer `-` (illegal, wrong)

````text
<answer>Qc8</answer>
````
