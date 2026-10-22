# qwen3-1.7b on dev500

- model: `Qwen/Qwen3-1.7B` @ `70d244cc86cc`
- profile: `qwen3-1.7b`
- git `90bfc56fc862`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T07:22:31Z, 39 s, cost $0.1432 ($3.040/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 5.8% [3.8, 8.0] |
| move accuracy | 10.2% [8.5, 12.0] |
| legal rate | 67.2% [64.4, 70.0] |
| format rate | 0.0% [0.0, 0.0] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 350 / 1024 |
| prompt tokens mean | 218 |
| hit max tokens | 9.7% |
| $ per 1k puzzles | 0.2864 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 31.0% |
| 600-799 | 42 | 19.0% |
| 800-999 | 42 | 11.9% |
| 1000-1199 | 42 | 4.8% |
| 1200-1399 | 42 | 0.0% |
| 1400-1599 | 42 | 0.0% |
| 1600-1799 | 42 | 2.4% |
| 1800-1999 | 42 | 0.0% |
| 2000-2199 | 41 | 0.0% |
| 2200-2399 | 41 | 0.0% |
| 2400-2599 | 41 | 0.0% |
| 2600-2799 | 41 | 0.0% |

## Examples

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `Re1+` (ok, right)

````text
… a corner.

### Evaluation:
- The white king is on e1, which is a very weak square for a king. It is surrounded by pawns and has no good squares to move to.
- The black king is on h8, which is a strong square, but it is also surrounded by pawns.
- The white queen is on e2, which is a strong square for the queen, but it is also surrounded by pawns.

### Best Move:
The best move for Black is to deliver checkmate. The only way to do this is to put the white king in a corner where it cannot escape.

Looking at the legal moves, the most promising move is **Re1+** (queen to e1, delivering check). This puts the white king in a corner (e1) and delivers check.

### Final Answer:
<answer>Re1+</answer>
````

**Kti9F-1** (rating 1497), solution `Nc4`, answer `Nc4` (ok, right)

````text
…ok for a move that threatens to deliver checkmate or significantly reduces the opponent's options. The position is:

```
8/1pp5/p1nkp3/1r1p4/3Pr3/P1P1nNp1/KP1Q2P1/2R5 b - - 8 40
```

Black's pieces are positioned to attack the white king, which is on e7. The white king is under significant pressure from the black pieces, especially the pawn on e5 and the knight on a5. The black queen is on d1, and the black rook on a5 is a strong attacking piece.

The best move is **Nc4+**, which delivers check and threatens to deliver checkmate. This move puts the white king in check and threatens to deliver checkmate by moving the knight to d5 or c5, depending on the king's movement.

<answer>Nc4+</answer>
````

**PwXh8-3** (rating 416), solution `Rxe1#`, answer `Be5` (ok, wrong)

````text
<answer>Be5</answer>
````

**Djqoz-1** (rating 1973), solution `Re3+`, answer `Re1` (ok, wrong)

````text
…t's a good move, but not the best.

#### 4. **Re4**:
- This is a good move, but it's not as strong as Re1 or Re2.

#### 5. **Rf5**:
- This is a good move, but it's not as strong as Re1 or Re2.

#### 6. **Rg5**:
- This is a good move, but it's not as strong as Re1 or Re2.

#### 7. **Rh5+**:
- This is a check, but it's not as strong as Re1 or Re2.

#### 8. **Rxa5**:
- This is a good move, but it's not as strong as Re1 or Re2.

#### 9. **a4**:
- This is a pawn move, not very strong.

#### 10. **d5**:
- This is a pawn move, not very strong.

---

### Best Move:
**Re1** is the strongest move, as it threatens to check the black king and supports the queen and rook on e1.

---

<answer>Re1</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (no_answer, wrong)

````text
… checkmate or puts the white king in a position where it's difficult to escape.

Looking at the legal moves, the most promising candidates are:

- **Qxh2#** (checkmate)
- **Qc5**, **Qc7**, **Qd7**, **Qd8**, **Qe5**, **Qe6**, **Qe7**, **Qf4**, **Qg3**, **Qxb4**, **Ra7**, **Rc8**, **Rd8**, **Re8**

The most immediate checkmate is **Qxh2#**, but this requires the queen to move to h2, which is not a legal move from the current position. The queen is on c7, so **Qc5** is a good candidate to threaten h2.

However, **Qxh2#** is a direct checkmate, and if the queen can move to h2, it would be a strong move. But the queen is on c7, so **Qc5** is a good move to threaten h2.

The best move is:

**Qc5**
````
