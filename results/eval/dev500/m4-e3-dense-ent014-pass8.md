# m4-e3-dense-ent014-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-24T23:34:40Z, 40 s, cost $0.0734 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 29.2% [25.2, 33.4] |
| move accuracy | 48.8% [45.8, 51.7] |
| legal rate | 98.6% [97.9, 99.3] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1056 [968, 1136] |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1468 |
| pass@k (T=1) | @1 28.0%, @4 39.3%, @8 45.0% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 83.3% |
| 600-799 | 42 | 83.3% |
| 800-999 | 42 | 59.5% |
| 1000-1199 | 42 | 40.5% |
| 1200-1399 | 42 | 28.6% |
| 1400-1599 | 42 | 14.3% |
| 1600-1799 | 42 | 16.7% |
| 1800-1999 | 42 | 4.8% |
| 2000-2199 | 41 | 9.8% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 2.4% |
| 2600-2799 | 41 | 4.9% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**XCRoR-3** (rating 1404), solution `Bc4+`, answer `Bc4+` (ok, right)

````text
<answer>Bc4+</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````

**o3C1e-1** (rating 2047), solution `Rc7`, answer `d5` (ok, wrong)

````text
<answer>d5</answer>
````

**G5pnn-1** (rating 1156), solution `Nd7#`, answer `-` (illegal, wrong)

````text
<answer>Nac4#</answer>
````
