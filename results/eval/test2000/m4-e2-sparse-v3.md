# m4-e2-sparse-v3 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `91af7e44bf9f`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-24T13:16:29Z, 26 s, cost $0.1888 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 28.0% [26.1, 30.0] |
| move accuracy | 44.3% [42.7, 45.9] |
| legal rate | 99.9% [99.8, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1038 [997, 1078] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0944 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 95.2% |
| 600-799 | 167 | 74.9% |
| 800-999 | 167 | 49.1% |
| 1000-1199 | 167 | 34.7% |
| 1200-1399 | 167 | 24.6% |
| 1400-1599 | 167 | 23.4% |
| 1600-1799 | 167 | 11.4% |
| 1800-1999 | 167 | 13.2% |
| 2000-2199 | 166 | 6.0% |
| 2200-2399 | 166 | 2.4% |
| 2400-2599 | 166 | 0.6% |
| 2600-2799 | 166 | 0.0% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1#</answer>
````

**oP1Yw-5** (rating 1436), solution `h3`, answer `h3` (ok, right)

````text
<answer>h3</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `cxd4` (ok, wrong)

````text
<answer> cxd4</answer>
````

**Oa7al-1** (rating 2132), solution `Kxf7`, answer `Rxa8` (ok, wrong)

````text
<answer>Rxa8#</answer>
````

**Kqb8P-3** (rating 659), solution `Rdxb1#`, answer `-` (illegal, wrong)

````text
<answer>Rxb1#</answer>
````
