# m4-e2-dense-v3 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `91af7e44bf9f`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-23T12:23:22Z, 27 s, cost $0.2078 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 25.8% [23.9, 27.8] |
| move accuracy | 43.2% [41.7, 44.7] |
| legal rate | 100.0% [99.9, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 973 [930, 1015] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1039 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 89.8% |
| 600-799 | 167 | 69.5% |
| 800-999 | 167 | 45.5% |
| 1000-1199 | 167 | 34.1% |
| 1200-1399 | 167 | 21.6% |
| 1400-1599 | 167 | 18.0% |
| 1600-1799 | 167 | 11.4% |
| 1800-1999 | 167 | 9.0% |
| 2000-2199 | 166 | 5.4% |
| 2200-2399 | 166 | 3.0% |
| 2400-2599 | 166 | 1.8% |
| 2600-2799 | 166 | 0.0% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1+</answer>
````

**bncHp-1** (rating 1419), solution `Rc1+`, answer `Rc1+` (ok, right)

````text
<answer>Rc1+</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**kYLXt-1** (rating 2023), solution `Qxd4+`, answer `Rxd1+` (ok, wrong)

````text
<answer>Rxd1+</answer>
````

**fw6hL-3** (rating 1163), solution `Qf1+`, answer `-` (illegal, wrong)

````text
<answer>Rxc2+</answer>
````
