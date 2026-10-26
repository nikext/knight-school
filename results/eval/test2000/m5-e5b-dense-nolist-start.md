# m5-e5b-dense-nolist-start on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b-nolist`, checkpoint `gs://knight-school-nt26-knight-school/runs/m4-sft-primer-m-t8/final/merged`
- git `7190e0411a2e`, prompt hash `49f43a62cf0a`, legal list off
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-26T11:40:10Z, 19 s, cost $0.1871 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 1.7% [1.1, 2.2] |
| move accuracy | 11.4% [10.5, 12.4] |
| legal rate | 71.1% [69.6, 72.6] |
| format rate | 91.4% [90.4, 92.4] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 9 / 10 |
| prompt tokens mean | 115 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.0936 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 5.4% |
| 600-799 | 167 | 3.6% |
| 800-999 | 167 | 2.4% |
| 1000-1199 | 167 | 2.4% |
| 1200-1399 | 167 | 0.0% |
| 1400-1599 | 167 | 1.8% |
| 1600-1799 | 167 | 1.8% |
| 1800-1999 | 167 | 0.6% |
| 2000-2199 | 166 | 0.6% |
| 2200-2399 | 166 | 0.0% |
| 2400-2599 | 166 | 0.0% |
| 2600-2799 | 166 | 1.2% |

## Examples

**W71jq-3** (rating 402), solution `Qxd1#`, answer `Qxd1#` (ok, right)

````text
<answer>Qxd1#</answer>
````

**jL1e8-3** (rating 1789), solution `Qxb8`, answer `Qxb8` (ok, right)

````text
<answer>Qxb8</answer>
````

**Sf0IA-1** (rating 559), solution `Qe8+`, answer `Rb2` (ok, wrong)

````text
<answer>Rb2</answer>
````

**tq3RW-3** (rating 1727), solution `Bxe2`, answer `Qf7` (ok, wrong)

````text
<answer>Qf7</answer>
````

**2IOMH-1** (rating 496), solution `Qe1#`, answer `-` (illegal, wrong)

````text
<answer>Qxf5</answer>
````
