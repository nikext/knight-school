# qwen3.5-2b-native on dev500

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b-native`
- git `90bfc56fc862`, prompt hash `b371401fde1c`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=native
- run: 2026-10-22T07:30:10Z, 80 s, cost $0.1067 ($3.040/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 0.0% [0.0, 0.0] |
| move accuracy | 0.0% [0.0, 0.0] |
| legal rate | 0.0% [0.0, 0.0] |
| format rate | 0.0% [0.0, 0.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 1024 / 1024 |
| prompt tokens mean | 211 |
| hit max tokens | 100.0% |
| $ per 1k puzzles | 0.2134 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 0.0% |
| 600-799 | 42 | 0.0% |
| 800-999 | 42 | 0.0% |
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

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (no_answer, wrong)

````text
…ng: `rb3rk1`
        *   a8: R
        *   b8: B
        *   c8: K
        *   d8: R
        *   e8: K
        *   f8: R
        *   g8: R
        *   h8: K
        *   Wait, `rb3rk1` is 6 characters.
        *   Let's look at the board again.
        *   `rb3rk1` -> a8: R, b8: B, c8: K, d8: R, e8: K, f8: R, g8: R, h8: K?
        *   Let's check the number of pieces.
        *   `rb3rk1` -> R, B, K, R, K, R, R, K? No.
        *   Let's look at the string again.
        *   `rb3rk1` -> a8: R, b8: B, c8: K, d8: R, e8: K, f8: R, g8: R, h8: K?
        *   Wait, the string is `rb3rk1`.
        *   Let's assume standard notation.
        *   `r` a8
        *   `b` b8
        *   `3`
        *   `r
````
