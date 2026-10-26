# m5-sft-primer-s-t8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T06:24:51Z, 7 s, cost $0.2145 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 25.0% [21.2, 29.0] |
| move accuracy | 41.2% [38.3, 44.2] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 966 [891, 1037] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.4290 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 90.5% |
| 600-799 | 42 | 78.6% |
| 800-999 | 42 | 54.8% |
| 1000-1199 | 42 | 31.0% |
| 1200-1399 | 42 | 7.1% |
| 1400-1599 | 42 | 9.5% |
| 1600-1799 | 42 | 7.1% |
| 1800-1999 | 42 | 9.5% |
| 2000-2199 | 41 | 7.3% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 2.4% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**jBbSv-1** (rating 1374), solution `Kxb5`, answer `Kxb5` (ok, right)

````text
<answer>Kxb5</answer>
````

**w6Jdl-1** (rating 593), solution `Qxf7`, answer `Kh7` (ok, wrong)

````text
<answer>Kh7</answer>
````

**BSF0r-1** (rating 2192), solution `f4`, answer `Nf2+` (ok, wrong)

````text
<answer>Nf2+</answer>
````
