# m4-e3-dense-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-24T02:28:02Z, 41 s, cost $0.0769 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 27.0% [23.2, 31.0] |
| move accuracy | 46.6% [43.6, 49.6] |
| legal rate | 97.7% [96.8, 98.5] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 994 [901, 1080] |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1537 |
| pass@k (T=1) | @1 26.6%, @4 37.6%, @8 42.8% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 71.4% |
| 600-799 | 42 | 83.3% |
| 800-999 | 42 | 54.8% |
| 1000-1199 | 42 | 42.9% |
| 1200-1399 | 42 | 28.6% |
| 1400-1599 | 42 | 14.3% |
| 1600-1799 | 42 | 11.9% |
| 1800-1999 | 42 | 4.8% |
| 2000-2199 | 41 | 2.4% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 4.9% |
| 2600-2799 | 41 | 2.4% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**k2iQC-3** (rating 1511), solution `Rxf8+`, answer `Rxf8+` (ok, right)

````text
<answer>Rxf8+</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````

**XPymD-3** (rating 2153), solution `Be6+`, answer `Rxf8+` (ok, wrong)

````text
<answer>Rxf8+</answer>
````

**XGGXr-1** (rating 508), solution `Rc8+`, answer `-` (illegal, wrong)

````text
<answer>c8=Q</answer>
````
