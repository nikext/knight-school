# m4-e3-sparse on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-24T10:30:42Z, 26 s, cost $0.1905 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 35.4% [33.4, 37.6] |
| move accuracy | 56.0% [54.5, 57.5] |
| legal rate | 99.8% [99.7, 99.9] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1237 [1199, 1276] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0953 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 95.8% |
| 600-799 | 167 | 85.0% |
| 800-999 | 167 | 73.7% |
| 1000-1199 | 167 | 54.5% |
| 1200-1399 | 167 | 44.9% |
| 1400-1599 | 167 | 24.6% |
| 1600-1799 | 167 | 14.4% |
| 1800-1999 | 167 | 15.6% |
| 2000-2199 | 166 | 7.2% |
| 2200-2399 | 166 | 3.6% |
| 2400-2599 | 166 | 3.6% |
| 2600-2799 | 166 | 1.8% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**kR1Fg-3** (rating 1536), solution `Rxh2`, answer `Rxh2` (ok, right)

````text
<answer>Rxh2</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**68ud2-5** (rating 2034), solution `Rf6`, answer `Qd8+` (ok, wrong)

````text
<answer>Qd8+</answer>
````

**IeMvW-3** (rating 1621), solution `R4f5+`, answer `-` (illegal, wrong)

````text
<answer>Rf5</answer>
````
