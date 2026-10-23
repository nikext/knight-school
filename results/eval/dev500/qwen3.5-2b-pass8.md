# qwen3.5-2b-pass8 on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`
- git `1a92ddf79865`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags; 8 samples at T=1.0 for pass@k
- run: 2026-10-23T20:45:05Z, 384 s, cost $0.4979 ($3.070/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 1.2% [0.4, 2.2] |
| move accuracy | 6.8% [5.4, 8.3] |
| legal rate | 46.0% [43.2, 48.9] |
| format rate | 62.9% [60.1, 65.7] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 396 / 1024 |
| prompt tokens mean | 218 |
| hit max tokens | 35.8% |
| $ per 1k puzzles | 0.9959 |
| pass@k (T=1) | @1 1.2%, @4 3.9%, @8 6.0% |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 2.4% |
| 600-799 | 42 | 7.1% |
| 800-999 | 42 | 4.8% |
| 1000-1199 | 42 | 0.0% |
| 1200-1399 | 42 | 0.0% |
| 1400-1599 | 42 | 0.0% |
| 1600-1799 | 42 | 0.0% |
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

**GvNDS-1** (rating 1595), solution `h4`, answer `h4` (ok, right)

````text
<answer>h4</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Be6` (ok, wrong)

````text
<answer>Be6</answer>
````

**2FNiR-1** (rating 1943), solution `a5`, answer `Kxe6` (ok, wrong)

````text
<answer>Kxe6</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (no_answer, wrong)

````text
…start.
            - FEN structure: `Core/Colors` `Time` `Pinning` `Ordinal`.
            - Or simply: `piece`/`file`square...
            - Let's assume the string `rb3rk1/1p3ppp/p1nq1n2/3p3B/1P1N4/P1N1P3/1B3PPP/R2Q1RK1 b - - 0 15` is the FEN.
            - Let's break the move string up.
            - `r` -> Rook on b3?
            - `b` -> Bishop? No, `b` is a pawn usually.
            - Let's try to interpret `rb3rk1` as `Rook` on `b3`, `Bishop` on... `1`?
            - Wait, the string is `rb3rk1`.
            - `r` (White Rook on b-file? No).
            - Let's look at the other side. `1B3PPP`. Two Bishops.
            - If White has `r` (Rook) and `1B3PPP` implies White has 2 bishops
````
