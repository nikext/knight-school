# m4-sft-primer-m-t8 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-23T20:37:51Z, 26 s, cost $0.0557 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 35.7% [33.6, 37.9] |
| move accuracy | 55.8% [54.3, 57.4] |
| legal rate | 100.0% [99.9, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1237 [1195, 1278] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0278 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 92.2% |
| 600-799 | 167 | 83.2% |
| 800-999 | 167 | 71.9% |
| 1000-1199 | 167 | 57.5% |
| 1200-1399 | 167 | 43.1% |
| 1400-1599 | 167 | 29.3% |
| 1600-1799 | 167 | 16.8% |
| 1800-1999 | 167 | 15.0% |
| 2000-2199 | 166 | 8.4% |
| 2200-2399 | 166 | 4.2% |
| 2400-2599 | 166 | 3.6% |
| 2600-2799 | 166 | 2.4% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**zbdOM-3** (rating 1418), solution `Qxe6`, answer `Qxe6` (ok, right)

````text
<answer>Qxe6</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**3FNw5-7** (rating 2194), solution `Kxb2`, answer `Bh7+` (ok, wrong)

````text
<answer>Bh7+</answer>
````

**T9ihg-3** (rating 2739), solution `Rh1`, answer `-` (illegal, wrong)

````text
<answer>Rh7</answer>
````
