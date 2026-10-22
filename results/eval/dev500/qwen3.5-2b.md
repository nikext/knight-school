# qwen3.5-2b on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`
- git `90bfc56fc862`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T07:19:54Z, 6 s, cost $0.2274 ($3.040/h)
- **rescored** 2026-10-22T07:58:47Z at git `f8ae0bebde20`: format no longer requires a think block in the completion when the chat template pre-fills one (ADR-017)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 5.4% [3.4, 7.4] |
| move accuracy | 15.9% [13.8, 18.1] |
| legal rate | 96.5% [95.2, 97.6] |
| format rate | 100.0% [100.0, 100.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 10 / 10 |
| prompt tokens mean | 218 |
| hit max tokens | 0.0% |
| $ per 1k puzzles | 0.4547 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 11.9% |
| 600-799 | 42 | 28.6% |
| 800-999 | 42 | 14.3% |
| 1000-1199 | 42 | 2.4% |
| 1200-1399 | 42 | 4.8% |
| 1400-1599 | 42 | 0.0% |
| 1600-1799 | 42 | 0.0% |
| 1800-1999 | 42 | 0.0% |
| 2000-2199 | 41 | 0.0% |
| 2200-2399 | 41 | 2.4% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 0.0% |

## Examples

**G3dim-1** (rating 479), solution `Qxb2#`, answer `Qxb2#` (ok, right)

````text
<answer>Qxb2#</answer>
````

**TZGMj-5** (rating 1689), solution `Ke5`, answer `Ke5` (ok, right)

````text
<answer>Ke5</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `Qxb4` (ok, wrong)

````text
<answer>Qxb4</answer>
````

**2FNiR-1** (rating 1943), solution `a5`, answer `Kxe6` (ok, wrong)

````text
<answer>Kxe6</answer>
````

**3InJC-1** (rating 549), solution `Rxe1#`, answer `-` (illegal, wrong)

````text
<answer>Re1</answer>
````
