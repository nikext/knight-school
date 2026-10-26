# m5-e4-dense on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T09:22:16Z, 26 s, cost $0.1918 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 29.5% [27.6, 31.6] |
| move accuracy | 46.9% [45.4, 48.5] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1068 [1024, 1111] |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0959 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 92.8% |
| 600-799 | 167 | 74.9% |
| 800-999 | 167 | 53.9% |
| 1000-1199 | 167 | 38.9% |
| 1200-1399 | 167 | 30.5% |
| 1400-1599 | 167 | 20.4% |
| 1600-1799 | 167 | 10.8% |
| 1800-1999 | 167 | 16.2% |
| 2000-2199 | 166 | 9.6% |
| 2200-2399 | 166 | 2.4% |
| 2400-2599 | 166 | 3.0% |
| 2600-2799 | 166 | 0.6% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**E5m1S-5** (rating 1423), solution `Rd2#`, answer `Rd2#` (ok, right)

````text
<answer>Rd2#</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**9QkvS-5** (rating 2102), solution `Qe4+`, answer `Rf7+` (ok, wrong)

````text
<answer>Rf7+</answer>
````
