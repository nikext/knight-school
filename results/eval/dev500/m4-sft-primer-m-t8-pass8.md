# m4-sft-primer-m-t8-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-23T20:40:37Z, 40 s, cost $0.0712 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 28.2% [24.4, 32.2] |
| move accuracy | 47.0% [44.1, 50.1] |
| legal rate | 98.8% [98.1, 99.4] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1046 [972, 1119] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1425 |
| pass@k (T=1) | @1 28.1%, @4 43.4%, @8 51.4% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 90.5% |
| 600-799 | 42 | 88.1% |
| 800-999 | 42 | 52.4% |
| 1000-1199 | 42 | 40.5% |
| 1200-1399 | 42 | 23.8% |
| 1400-1599 | 42 | 7.1% |
| 1600-1799 | 42 | 14.3% |
| 1800-1999 | 42 | 4.8% |
| 2000-2199 | 41 | 9.8% |
| 2200-2399 | 41 | 2.4% |
| 2400-2599 | 41 | 2.4% |
| 2600-2799 | 41 | 0.0% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**ehLrM-3** (rating 1473), solution `Qxc5`, answer `Qxc5` (ok, right)

````text
<answer>Qxc5</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````

**wxqE3-5** (rating 2050), solution `fxe4`, answer `Nxd4` (ok, wrong)

````text
<answer>Nxd4</answer>
````

**G5pnn-1** (rating 1156), solution `Nd7#`, answer `-` (illegal, wrong)

````text
<answer>Nac4#</answer>
````
