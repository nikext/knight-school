# m5-sft-rules-m-t9-10-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-26T02:14:43Z, 41 s, cost $0.0761 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 2.0% [0.8, 3.2] |
| move accuracy | 12.0% [9.9, 14.0] |
| legal rate | 58.0% [54.8, 61.0] |
| format rate | 99.7% [99.4, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.1522 |
| pass@k (T=1) | @1 2.0%, @4 5.2%, @8 7.6% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 4.8% |
| 600-799 | 42 | 4.8% |
| 800-999 | 42 | 4.8% |
| 1000-1199 | 42 | 2.4% |
| 1200-1399 | 42 | 0.0% |
| 1400-1599 | 42 | 0.0% |
| 1600-1799 | 42 | 2.4% |
| 1800-1999 | 42 | 2.4% |
| 2000-2199 | 41 | 0.0% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 2.4% |

## Examples

**DWbM5-3** (rating 529), solution `Rxe8#`, answer `Rxe8#` (ok, right)

````text
<answer>Rxe8#</answer>
````

**EHmZh-3** (rating 1871), solution `Qxf3`, answer `Qxf3` (ok, right)

````text
<answer>Qxf3</answer>
````

**G3dim-1** (rating 479), solution `Qxb2#`, answer `Qxf3` (ok, wrong)

````text
<answer>Qxf3</answer>
````

**Ulzg9-5** (rating 1942), solution `e5`, answer `Kg6` (ok, wrong)

````text
<answer>Kg6</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (illegal, wrong)

````text
<answer>Qxf2+</answer>
````
