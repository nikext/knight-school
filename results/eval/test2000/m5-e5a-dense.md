# m5-e5a-dense on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T05:13:10Z, 30 s, cost $0.2011 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 26.2% [24.3, 28.1] |
| move accuracy | 43.5% [42.0, 45.1] |
| legal rate | 99.8% [99.6, 99.9] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 995 [954, 1035] |
| response tokens mean / p95 | 10 / 13 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1005 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 91.0% |
| 600-799 | 167 | 75.4% |
| 800-999 | 167 | 43.7% |
| 1000-1199 | 167 | 36.5% |
| 1200-1399 | 167 | 22.2% |
| 1400-1599 | 167 | 16.8% |
| 1600-1799 | 167 | 8.4% |
| 1800-1999 | 167 | 12.0% |
| 2000-2199 | 166 | 4.2% |
| 2200-2399 | 166 | 1.8% |
| 2400-2599 | 166 | 1.2% |
| 2600-2799 | 166 | 0.6% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
Qe1# <answer>Qe1#</answer>
````

**DV3YR-3** (rating 1400), solution `Qxe8#`, answer `Qxe8#` (ok, right)

````text
<answer>Qxe8#</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**ZGgow-5** (rating 2128), solution `Rxe3`, answer `Re8+` (ok, wrong)

````text
<answer>Re8+</answer>
````

**zWJ1Q-1** (rating 1186), solution `Rf7`, answer `-` (illegal, wrong)

````text
<answer>Rg5</answer>
````
