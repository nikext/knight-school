# m4-e3-dense-ent014 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-24T23:32:53Z, 26 s, cost $0.1894 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 34.8% [32.6, 36.9] |
| move accuracy | 55.6% [54.1, 57.1] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1214 [1173, 1254] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0947 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 92.8% |
| 600-799 | 167 | 83.2% |
| 800-999 | 167 | 70.7% |
| 1000-1199 | 167 | 56.3% |
| 1200-1399 | 167 | 40.1% |
| 1400-1599 | 167 | 25.7% |
| 1600-1799 | 167 | 13.8% |
| 1800-1999 | 167 | 15.6% |
| 2000-2199 | 166 | 7.8% |
| 2200-2399 | 166 | 5.4% |
| 2400-2599 | 166 | 2.4% |
| 2600-2799 | 166 | 2.4% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**ud5K1-5** (rating 1484), solution `Kxh7`, answer `Kxh7` (ok, right)

````text
<answer>Kxh7</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**A2jEo-3** (rating 2028), solution `Kd7`, answer `Kd5` (ok, wrong)

````text
<answer>Kd5</answer>
````
