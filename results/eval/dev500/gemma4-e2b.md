# gemma4-e2b on dev500

- model: `google/gemma-4-E2B-it` @ `3e22461f65e8`
- profile: `gemma4-e2b`
- git `90bfc56fc862`, prompt hash `c728de49e119`, legal list on
- decoding: greedy (T=0), max 1024 tokens, think=tags
- run: 2026-10-22T07:27:48Z, 75 s, cost $0.2821 ($3.040/h)

500 puzzles, 1163 positions. 95% bootstrap CIs over puzzles.

| Metric | Value |
|---|---|
| solve rate | 0.4% [0.0, 1.0] |
| move accuracy | 4.0% [2.9, 5.1] |
| legal rate | 20.6% [18.2, 22.9] |
| format rate | 20.1% [17.8, 22.5] |
| puzzle rating (50% solve) | < range |
| response tokens mean / p95 | 995 / 1024 |
| prompt tokens mean | 202 |
| hit max tokens | 69.4% |
| $ per 1k puzzles | 0.5642 |

| Rating bin | n | solve |
|---|---|---|
| 400-599 | 42 | 2.4% |
| 600-799 | 42 | 2.4% |
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

**6cnND-3** (rating 526), solution `Rxg4+`, answer `Rxg4+` (ok, right)

````text
…plays. For example, if 63. Rg3, Black can play 63... Qg5, maintaining pressure.

Comparing the options, 63. Rxg4+ immediately simplifies the position into a drawn King vs King endgame, which is the best practical outcome for White in this losing scenario.

Let's verify the line after 63. Rxg4+ Kxg4:
White to move. White has Kg1, Black has Kg4.
If 64. Kh2, Black plays 64... Kf3. White plays 65. Kh1. Black plays 65... Ke2. White plays 66. Kh2. This looks like a standard draw setup where White tries to keep the King centralized or away from the edge. Since the material is equalized to K vs K, the game is drawn.

Therefore, 63. Rxg4+ is the winning (drawing) move.
</think>
<answer>Rxg4+</answer>
````

**mnxTy-1** (rating 1715), solution `Rxf2+`, answer `Rxf2+` (ok, right)

````text
…s in such positions.

If we look at the immediate threats: White's queen on d1 is somewhat passive. Black needs to exploit the exposed king or the weak pawns.

The move 21... Rxf2+ seems the most promising way to disrupt White's coordination and exploit the slightly awkward king position (g1).

Let's confirm the line 21... Rxf2+ 22. Kg1 Qg3+ 23. Kh1. Black is slightly better due to the active pieces and potential for further infiltration.

If Black plays a quieter move like ...b5, White might consolidate with Qd2 or Qc1, and the initiative might slip away.

Therefore, the forcing tactical shot is the best approach.
</think>
Rxf2+ is the most forcing and promising move.
<answer>Rxf2+</answer>
````

**Ku5Hq-1** (rating 510), solution `Re1+`, answer `a5` (ok, wrong)

````text
…s preference. In these endgames/middlegames, improving the structure or creating space is often key.

Comparing ...a5 and ...c5:
...c5 immediately challenges the center/queenside structure.
...a5 is more positional.

Given the options, **... a5** seems the most flexible and solid improvement, preparing for the long game. It prevents White from playing anything too aggressive on the queenside immediately.

Let's verify the move list provided: Ba2, Bb3, Bc4, Be4, Be6, Bf3, Bg2, Bh1, Kf8, Kg8, Kh8, Ra8, Rb8, Rc8, Rd8, Re1+, Re2, Re3, Re4, Re5, Re6, Re7, Rf8, Rg8, Rh8, a5, c5, g5, h5, h6.

I will select the most structurally sound move that improves Black's position.
<answer>a5</answer>
</think>
````

**Ulzg9-3** (rating 1942), solution `f6`, answer `Kf6` (ok, wrong)

````text
…The position remains balanced, but Black has improved coordination.

If Black plays **61... Kg5**:
White might play 62. Kd3. Black can play 62... Kf6. This transposes back to lines involving Kf6, but perhaps slightly less direct.

Stockfish evaluation strongly favors king centralization. Kf6 seems the most flexible and strongest way to improve the position without committing to a pawn break prematurely. It prepares for any future action.

Let's check the engine preference. Stockfish 16.1 at depth 30+ confirms that Kf6 is the top choice, leading to a draw (0.00).

Engine lines:
1. Kf6 (0.00)
2. Kg5 (-0.05)
3. Kg6 (-0.05)

Kf6 is the most solid and improving move.
</think>
<answer>Kf6</answer>
````

**fMA5s-1** (rating 589), solution `Qxh2#`, answer `-` (no_answer, wrong)

````text
…on is: `rb3rk1/1p3ppp/p1nq1n2/3p3B/1P1N4/1P11P3/1B3PPP/R2Q1RK1 b - - 0 15` -> `rb3rk1/1p3ppp/p1nq1n2/3p3B/1P1N4/1P11P3/1B3PPP/R2Q1RK1 b - - 0 15`.
If 15... Nxb4 16. axb4, the board state is: White has doubled pawns on the b-file if the a-pawn is captured later, but here White has a passed pawn on b4. Black has a solid position.

Let's check engine evaluations. Stockfish strongly prefers material gain or positional improvements that lead to an advantage.

If we look at the immediate tactical possibilities, 15... Nxb4 seems like the strongest practical choice, forcing White to make structural concessions or accept the material deficit.

Let's re-examine the move list provided. `Nxb4` is listed
````
