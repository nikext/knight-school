# m5-sft-primer-s-t8-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-26T06:29:32Z, 41 s, cost $0.0753 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 17.8% [14.6, 21.4] |
| move accuracy | 31.1% [28.4, 33.9] |
| legal rate | 97.0% [95.9, 98.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 747 [637, 838] |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1506 |
| pass@k (T=1) | @1 18.1%, @4 25.8%, @8 31.8% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 66.7% |
| 600-799 | 42 | 59.5% |
| 800-999 | 42 | 33.3% |
| 1000-1199 | 42 | 23.8% |
| 1200-1399 | 42 | 9.5% |
| 1400-1599 | 42 | 4.8% |
| 1600-1799 | 42 | 7.1% |
| 1800-1999 | 42 | 2.4% |
| 2000-2199 | 41 | 4.9% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 0.0% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**dBRxL-5** (rating 1372), solution `Kxc6`, answer `Kxc6` (ok, right)

````text
<answer>Kxc6</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````

**4zwv3-3** (rating 1800), solution `Bxg5`, answer `Bxd6` (ok, wrong)

````text
<answer>Bxd6</answer>
````

**bYV92-1** (rating 589), solution `Qf1+`, answer `-` (illegal, wrong)

````text
<answer>Rf1</answer>
````
