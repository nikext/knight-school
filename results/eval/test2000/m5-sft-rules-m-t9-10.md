# m5-sft-rules-m-t9-10 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `7190e0411a2e`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T02:11:33Z, 27 s, cost $0.0604 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 2.9% [2.1, 3.6] |
| move accuracy | 15.6% [14.6, 16.6] |
| legal rate | 68.7% [67.1, 70.4] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 8 / 10 |
| prompt tokens mean | 219 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0302 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 10.8% |
| 600-799 | 167 | 7.8% |
| 800-999 | 167 | 3.6% |
| 1000-1199 | 167 | 4.8% |
| 1200-1399 | 167 | 1.2% |
| 1400-1599 | 167 | 1.2% |
| 1600-1799 | 167 | 0.6% |
| 1800-1999 | 167 | 0.6% |
| 2000-2199 | 166 | 1.2% |
| 2200-2399 | 166 | 2.4% |
| 2400-2599 | 166 | 0.0% |
| 2600-2799 | 166 | 0.0% |

## Examples

**Sf0IA-3** (rating 559), solution `Rxe8#`, answer `Rxe8#` (ok, right)

````text
<answer>Rxe8#</answer>
````

**IzZ7y-3** (rating 1636), solution `Qxg5`, answer `Qxg5` (ok, right)

````text
<answer>Qxg5</answer>
````

**hXsXh-1** (rating 518), solution `Rd8#`, answer `Bc6+` (ok, wrong)

````text
<answer>Bc6+</answer>
````

**wzozw-3** (rating 1869), solution `Rd1+`, answer `Qxe3` (ok, wrong)

````text
<answer>Qxe3</answer>
````

**2IOMH-1** (rating 496), solution `Qe1#`, answer `-` (illegal, wrong)

````text
<answer>Qxf5</answer>
````
