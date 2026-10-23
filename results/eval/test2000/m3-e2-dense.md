# m3-e2-dense on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `gs://knight-school-nt26-knight-school/runs/m3-e2-dense/final/merged`
- git `25b5dd417d43`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T18:33:59Z, 94 s, cost $0.0462 ($0.541/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 23.8% [21.9, 25.7] |
| move accuracy | 41.8% [40.3, 43.3] |
| legal rate | 100.0% [99.9, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 873 [816, 927] |
| response tokens mean / p95 | 9 / 11 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0231 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 74.3% |
| 600-799 | 167 | 67.1% |
| 800-999 | 167 | 41.9% |
| 1000-1199 | 167 | 29.3% |
| 1200-1399 | 167 | 21.0% |
| 1400-1599 | 167 | 17.4% |
| 1600-1799 | 167 | 9.0% |
| 1800-1999 | 167 | 10.2% |
| 2000-2199 | 166 | 6.6% |
| 2200-2399 | 166 | 4.8% |
| 2400-2599 | 166 | 2.4% |
| 2600-2799 | 166 | 1.2% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
<answer>Qe1</answer>
````

**yuoIH-3** (rating 1532), solution `Nxc6`, answer `Nxc6` (ok, right)

````text
<answer>Nxc6</answer>
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `cxd4` (ok, wrong)

````text
<answer>cxd4</answer>
````

**wKAmH-1** (rating 2118), solution `Rxf1+`, answer `exd4` (ok, wrong)

````text
<answer>exd4</answer>
````

**HVNNm-3** (rating 2402), solution `Rxg6`, answer `-` (illegal, wrong)

````text
<answer>Nxg6</answer>
````
