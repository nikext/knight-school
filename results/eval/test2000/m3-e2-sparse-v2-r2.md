# m3-e2-sparse-v2-r2 on test2000

- model: `Qwen/Qwen3.5-2B` @ `15852e8c1636`
- profile: `qwen3.5-2b`, checkpoint `/tmp/ks-work/final/merged`
- git `35e9bf043759`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-23T08:20:35Z, 369 s, cost $0.4990 ($3.070/h)

2000 puzzles, 4684 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 23.5% [21.6, 25.4] |
| move accuracy | 38.7% [37.2, 40.3] |
| legal rate | 98.1% [97.7, 98.6] |
| format rate | 99.9% [99.7, 100.0] |
| puzzle rating (50% solve) | 917 [873, 958] |
| response tokens mean / p95 | 1023 / 1024 |
| prompt tokens mean | 219 |
| hit max tokens | 99.8% |
| $ per 1k puzzles | 0.2495 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 167 | 84.4% |
| 600-799 | 167 | 66.5% |
| 800-999 | 167 | 45.5% |
| 1000-1199 | 167 | 31.7% |
| 1200-1399 | 167 | 18.0% |
| 1400-1599 | 167 | 10.8% |
| 1600-1799 | 167 | 5.4% |
| 1800-1999 | 167 | 9.0% |
| 2000-2199 | 166 | 9.0% |
| 2200-2399 | 166 | 1.2% |
| 2400-2599 | 166 | 0.0% |
| 2600-2799 | 166 | 0.0% |

## Examples

**2IOMH-1** (rating 496), solution `Qe1#`, answer `Qe1#` (ok, right)

````text
… `3` (empty), `b` (b3), `P` (c3), `1` (empty), `r` (d3? No, `r` is Rook).
                *   Let's assume the string is: `p` `3` `b` `P` `1` `r` ...
                *   This looks like:
                    *   Rank 1: `p` (a3), `3` (empty), `b` (b3), `P` (c3), `1` (empty), `r` (d3? No, `r` is Rook).
                    *   Let's try to map standard pieces.
                    *   `p` = White Pawn
                    *   `b` = Black Pawn
                    *   `P` = White Pawn
                    *   `r` = Black Rook
                    *   `1` = Empty square
                    *   `5k2` -> This is the start of the string? No, the string starts with `5k2`.
                    *   Ah, the F
````

**Nf451-3** (rating 1304), solution `fxe5`, answer `fxe5` (ok, right)

````text
…  **Wait, the FEN says `4P3` on rank 2**. This means 4 White pawns, 3 Black pawns.
            *   **Total White Material**: 11 pawns + King + Queen + Rook + Bishop + Knight.
            *   **Total Black Material**: 8 pawns + King + Rook + Knight.
            *   **Material Advantage**: White has a huge material lead (approx 11 pawns vs 8 pawns + 1 Knight + 1 Rook + 1 King).
            *   **Position**: White to move. The FEN provided is `8/4P3/6p1/3Krk1p/5P1P/8/8/8`.
            *   **Wait, I misread the FEN structure completely.** Let's re-parse standard FEN.
                *   `8/4P3/6p1/3Krk1p/5P1P/8/8/8`
                *   Piece 1 (Rank 1): 8 empty.
                *   Piece 2 (Rank
````

**b3ic0-1** (rating 522), solution `Qxf7+`, answer `Bxf7+` (ok, wrong)

````text
…P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P, P
````

**z8ijt-1** (rating 2002), solution `Nxg3`, answer `Bxc4` (ok, wrong)

````text
… King, Black Pawn? No.
                *   Let's assume the provided FEN is:
                    *   Rank 8: `r2r2k1` (Black Rook, Black Pawn, Black Rook, Black Pawn, Black King, Black Pawn? No, `k` is King. `r` is Rook. `P` is Pawn. `r` is Rook. `2` is Pawn. `k` is King. `1` is Pawn? No, `1` is empty? No, `1` is a piece? No, `1` is a number.
                    *   Let's look at the pieces again.
                    *   `r2r2k1` -> `r` (Rook), `2` (Pawn), `r` (Rook), `2` (Pawn), `k` (King), `1` (Pawn? No, `1` is a number. Wait, FEN is `r2r2k1`. That's 6 chars. `r` `2` `r` `2` `k` `1`.
                    *   Let's assume the standard:
                        *   Rank 8: `r` (Black Rook), `2
````

**Kqb8P-3** (rating 659), solution `Rdxb1#`, answer `-` (illegal, wrong)

````text
…wns, `2` is 2 pawns? No. `2P` means 2 pawns. `2P2P2` means 2, 2, 2 pawns? No.
                    *   Let's count: `2NB4` -> 2N, 1B, 4P.
                    *   `2P2P2` -> 2P, 2P, 2P? No. The string is `2P2P2`.
                    *   Let's re-read the FEN: `1r6/6k1/p5p1/2NB4/2P2P2/8/P7/KR1r4`
                    *   Maybe the spaces are missing? No, spaces separate files.
                    *   Let's try to map files to ranks.
                    *   Rank 8: `P7` -> This is likely `P` at file 7 (f8)? No, `P` is a piece. `7` is a file.
                    *   Okay, let's assume the FEN is:
                        *   Rank 8: `P` (a8), `7` (b8)... No.
                        *   Let's assume
````
