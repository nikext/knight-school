# qwen3-1.7b-native on dev500

- model: `Qwen/Qwen3-1.7B` @ `70d244cc86cc`
- profile: `qwen3-1.7b-native`
- git `90bfc56fc862`, prompt hash `b371401fde1c`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=native
- run: 2026-10-22T07:32:41Z, 95 s, cost $0.1219 ($3.040/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 0.0% [0.0, 0.0] |
| move accuracy | 0.0% [0.0, 0.0] |
| legal rate | 0.0% [0.0, 0.0] |
| format rate | 0.0% [0.0, 0.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 1024 / 1024 |
| prompt tokens mean | 209 |
| hit max tokens | 100.0% |
| $ per 1k puzzles | 0.2437 |

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
…squares between them. So, for example, in the first line, "rb3rk1" would be:

- r (rook)
- b (bishop)
- 3 (three squares between them)
- r (rook)
- k (king)
- 1 (the file, but maybe that's the rank? Wait, no. Wait, the FEN is written as:

Each rank is a string of the form [pieces][number of squares][pieces][number of squares]... etc. So, for example, the first line is rank 8 (the bottom), and the first part is "rb3rk1". Let's break it down:

The first part is "rb3rk1". So, the pieces are r, b, 3, r, k, 1. Wait, but that would be 6 characters. Wait, maybe the numbers are between the pieces. So, the first part is the pieces, then the numbers between them. So, for example, "rb3rk1" would be:

-
````
