# m4-e3-sparse-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-24T10:32:57Z, 40 s, cost $0.0746 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 28.2% [24.4, 32.4] |
| move accuracy | 47.8% [44.8, 50.8] |
| legal rate | 89.8% [88.0, 91.5] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1037 [952, 1118] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1491 |
| pass@k (T=1) | @1 28.4%, @4 40.5%, @8 47.0% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 81.0% |
| 600-799 | 42 | 85.7% |
| 800-999 | 42 | 57.1% |
| 1000-1199 | 42 | 40.5% |
| 1200-1399 | 42 | 28.6% |
| 1400-1599 | 42 | 14.3% |
| 1600-1799 | 42 | 11.9% |
| 1800-1999 | 42 | 4.8% |
| 2000-2199 | 41 | 4.9% |
| 2200-2399 | 41 | 2.4% |
| 2400-2599 | 41 | 2.4% |
| 2600-2799 | 41 | 2.4% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**Kti9F-5** (rating 1497), solution `Nxb2`, answer `Nxb2` (ok, right)

````text
<answer>Nxb2</answer>
````

**XuVi0-1** (rating 588), solution `Re1+`, answer `Rb8` (ok, wrong)

````text
<answer>Rb8</answer>
````

**4AAn9-3** (rating 2174), solution `exf3`, answer `Bc5+` (ok, wrong)

````text
<answer>Bc5+</answer>
````

**XGGXr-1** (rating 508), solution `Rc8+`, answer `-` (illegal, wrong)

````text
<answer>cg8=Q#</answer>
````
