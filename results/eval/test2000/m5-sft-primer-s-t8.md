# m5-sft-primer-s-t8 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T06:26:19Z, 26 s, cost $0.0597 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 25.5% [23.6, 27.5] |
| move accuracy | 41.9% [40.5, 43.4] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 971 [927, 1012] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0299 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 85.6% |
| 600-799 | 167 | 72.5% |
| 800-999 | 167 | 48.5% |
| 1000-1199 | 167 | 33.5% |
| 1200-1399 | 167 | 21.6% |
| 1400-1599 | 167 | 17.4% |
| 1600-1799 | 167 | 9.0% |
| 1800-1999 | 167 | 9.6% |
| 2000-2199 | 166 | 4.2% |
| 2200-2399 | 166 | 3.6% |
| 2400-2599 | 166 | 0.0% |
| 2600-2799 | 166 | 0.0% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**ac9fj-1** (rating 1569), solution `Rxd4`, answer `Rxd4` (ok, right)

````text
<answer>Rxd4</answer>
````

**Vvq06-1** (rating 419), solution `Rd8+`, answer `gxf4` (ok, wrong)

````text
<answer>gxf4</answer>
````

**7WbZf-3** (rating 2153), solution `Qg3+`, answer `Rxf1+` (ok, wrong)

````text
<answer>Rxf1+</answer>
````
