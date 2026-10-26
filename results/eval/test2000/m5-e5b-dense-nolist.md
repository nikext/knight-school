# m5-e5b-dense-nolist on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b-nolist`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `49f43a62cf0a`, legal list off
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T11:32:58Z, 16 s, cost $0.1866 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 1.9% [1.4, 2.5] |
| move accuracy | 14.3% [13.2, 15.4] |
| legal rate | 87.8% [86.7, 88.9] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 8 / 9 |
| prompt tokens mean | 115 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0933 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 5.4% |
| 600-799 | 167 | 3.0% |
| 800-999 | 167 | 3.6% |
| 1000-1199 | 167 | 3.0% |
| 1200-1399 | 167 | 1.8% |
| 1400-1599 | 167 | 0.6% |
| 1600-1799 | 167 | 1.2% |
| 1800-1999 | 167 | 0.6% |
| 2000-2199 | 166 | 1.8% |
| 2200-2399 | 166 | 0.6% |
| 2400-2599 | 166 | 0.6% |
| 2600-2799 | 166 | 0.6% |

## Examples

**W71jq-3** (rating 402), solution `Qxd1#`, answer `Qxd1#` (ok, right)

````text
<answer>Qxd1</answer>
````

**S11un-1** (rating 1847), solution `dxe7`, answer `dxe7` (ok, right)

````text
<answer>dxe7</answer>
````

**2IOMH-1** (rating 496), solution `Qe1#`, answer `b3` (ok, wrong)

````text
<answer>b3</answer>
````

**coHoW-1** (rating 1717), solution `Qxe1`, answer `Qf4` (ok, wrong)

````text
<answer>Qf4</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `-` (illegal, wrong)

````text
<answer>Qxf1</answer>
````
