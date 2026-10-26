# m5-e5a-dense-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-26T05:17:23Z, 44 s, cost $0.0793 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 27.4% [23.6, 31.4] |
| move accuracy | 44.9% [41.8, 48.0] |
| legal rate | 98.8% [98.1, 99.4] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1011 [924, 1089] |
| response tokens mean / p95 | 10 / 15 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1587 |
| pass@k (T=1) | @1 27.6%, @4 29.4%, @8 30.2% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 88.1% |
| 600-799 | 42 | 85.7% |
| 800-999 | 42 | 47.6% |
| 1000-1199 | 42 | 40.5% |
| 1200-1399 | 42 | 21.4% |
| 1400-1599 | 42 | 11.9% |
| 1600-1799 | 42 | 11.9% |
| 1800-1999 | 42 | 2.4% |
| 2000-2199 | 41 | 4.9% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 7.3% |
| 2600-2799 | 41 | 4.9% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**OgWh4-5** (rating 1398), solution `Bxd1`, answer `Bxd1` (ok, right)

````text
<answer>Bxd1</answer>
````

**bYV92-1** (rating 589), solution `Qf1+`, answer `Qe1+` (ok, wrong)

````text
Qg1+, Qxg2+ <answer>Qe1+</answer>
````

**BSF0r-3** (rating 2192), solution `gxf4`, answer `Nf2+` (ok, wrong)

````text
Nxf2, <answer>Nf2+</answer>
````

**cNL4A-1** (rating 560), solution `Rf8+`, answer `-` (illegal, wrong)

````text
<answer>Rg7</answer>
````
