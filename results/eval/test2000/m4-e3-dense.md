# m4-e3-dense on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-24T02:23:55Z, 27 s, cost $0.2005 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 32.6% [30.5, 34.7] |
| move accuracy | 54.5% [53.1, 56.1] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1151 [1107, 1194] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1002 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 87.4% |
| 600-799 | 167 | 79.6% |
| 800-999 | 167 | 65.3% |
| 1000-1199 | 167 | 49.7% |
| 1200-1399 | 167 | 40.1% |
| 1400-1599 | 167 | 22.2% |
| 1600-1799 | 167 | 14.4% |
| 1800-1999 | 167 | 16.2% |
| 2000-2199 | 166 | 7.2% |
| 2200-2399 | 166 | 4.2% |
| 2400-2599 | 166 | 3.0% |
| 2600-2799 | 166 | 1.2% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**t9r9x-3** (rating 1586), solution `g4+`, answer `g4+` (ok, right)

````text
<answer>g4+</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**nezZF-1** (rating 2197), solution `Kh8`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````
