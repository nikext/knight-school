# m3-e2-dense-v2 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `35e9bf043759`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T22:11:52Z, 26 s, cost $0.1924 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 27.2% [25.2, 29.1] |
| move accuracy | 43.6% [42.1, 45.2] |
| legal rate | 100.0% [99.9, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1011 [967, 1053] |
| response tokens mean / p95 | 10 / 11 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0962 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 88.0% |
| 600-799 | 167 | 73.7% |
| 800-999 | 167 | 49.7% |
| 1000-1199 | 167 | 38.9% |
| 1200-1399 | 167 | 25.7% |
| 1400-1599 | 167 | 15.6% |
| 1600-1799 | 167 | 9.6% |
| 1800-1999 | 167 | 10.8% |
| 2000-2199 | 166 | 8.4% |
| 2200-2399 | 166 | 3.6% |
| 2400-2599 | 166 | 1.2% |
| 2600-2799 | 166 | 0.0% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1</answer>
````

**im9qY-1** (rating 1446), solution `Ba6+`, answer `Ba6+` (ok, right)

````text
<answer>Ba6+</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
<answer>Bxf7+</answer>
````

**uqHKj-1** (rating 2088), solution `exd5`, answer `Rxc4` (ok, wrong)

````text
<answer>Rxc4</answer>
````

**OVay3-1** (rating 979), solution `Qh5+`, answer `-` (illegal, wrong)

````text
<answer>h5</answer>
````
