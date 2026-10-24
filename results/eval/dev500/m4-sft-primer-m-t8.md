# m4-sft-primer-m-t8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-23T20:36:34Z, 6 s, cost $0.1943 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 35.2% [31.0, 39.6] |
| move accuracy | 56.4% [53.5, 59.4] |
| legal rate | 100.0% [100.0, 100.0] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | 1223 [1151, 1298] |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.3886 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 97.6% |
| 600-799 | 42 | 85.7% |
| 800-999 | 42 | 81.0% |
| 1000-1199 | 42 | 54.8% |
| 1200-1399 | 42 | 35.7% |
| 1400-1599 | 42 | 23.8% |
| 1600-1799 | 42 | 11.9% |
| 1800-1999 | 42 | 9.5% |
| 2000-2199 | 41 | 7.3% |
| 2200-2399 | 41 | 2.4% |
| 2400-2599 | 41 | 4.9% |
| 2600-2799 | 41 | 4.9% |

## Examples

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxh2#` (ok, right)

````text
<answer>Qxh2#</answer>
````

**vguWo-3** (rating 1424), solution `Qxc4+`, answer `Qxc4+` (ok, right)

````text
<answer>Qxc4+</answer>
````

**cNL4A-1** (rating 560), solution `Rf8+`, answer `Rxa7+` (ok, wrong)

````text
<answer>Rxa7+</answer>
````

**fRmwq-1** (rating 2009), solution `Qh6`, answer `Nf6+` (ok, wrong)

````text
<answer>Nf6+</answer>
````
