# m5-sft-rules-m-t9-10 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T02:10:05Z, 7 s, cost $0.2150 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 3.8% [2.2, 5.6] |
| move accuracy | 15.3% [13.2, 17.6] |
| legal rate | 69.6% [66.3, 72.7] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.4299 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 14.3% |
| 600-799 | 42 | 16.7% |
| 800-999 | 42 | 2.4% |
| 1000-1199 | 42 | 0.0% |
| 1200-1399 | 42 | 2.4% |
| 1400-1599 | 42 | 2.4% |
| 1600-1799 | 42 | 7.1% |
| 1800-1999 | 42 | 0.0% |
| 2000-2199 | 41 | 0.0% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 0.0% |

## Examples

**w6Jdl-1** (rating 593), solution `Qxf7`, answer `Qxf7` (ok, right)

````text
<answer>Qxf7</answer>
````

**oibo2-1** (rating 1626), solution `Rc5`, answer `Rc5` (ok, right)

````text
<answer>Rc5</answer>
````

**G3dim-1** (rating 479), solution `Qxb2#`, answer `Qxf3` (ok, wrong)

````text
<answer>Qxf3</answer>
````

**mcNF1-7** (rating 1849), solution `Qxg2+`, answer `Qxe1+` (ok, wrong)

````text
<answer>Qxe1+</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (illegal, wrong)

````text
<answer>Qxc3</answer>
````
