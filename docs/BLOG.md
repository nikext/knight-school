# A chess primer beats RL, at 2B parameters and $197

*Draft, M6. Where it gets posted is the author's call. Every number here comes from
[RESULTS.md](RESULTS.md), where each one sits next to the prediction I wrote before the run.*

## The question

Last year [Chess-R1](https://arxiv.org/abs/2507.00726) trained 3–8B language models with GRPO on
Lichess puzzles. All of them plateaued at around 25–30% puzzle accuracy. With a sparse "right move
or not" reward, the 3B model didn't learn at all. The authors' reading was that the base models
don't know enough chess (0% on a board-state probe), and reinforcement learning can sharpen what a
model knows but not teach it something new.

If that's right, there's a cheap fix to test: give the model the knowledge first. Not with
distilled reasoning traces from a bigger LLM, which would muddy the question, but with a
**teacher-free primer**: supervised fine-tuning on questions whose answers a chess library or
an engine can compute. What's on e4? What are the legal moves? What's the FEN after Nxe5? What's
Stockfish's best move here? Then run the same GRPO on top and see whether the ceiling moves.

I ran it on one model, Qwen3.5-2B, with $600 of Google Cloud credits that I wasn't allowed to
exceed, and I wrote every prediction down before each run.

## Setup

**Data.** The Lichess puzzle database (CC0), split by source game into training puzzles, a dev
set of 500 and a test set of 2,000, stratified over twelve rating bins from 400 to 2799. The RL
set is 66,008 solver positions. For each one, Stockfish 19 scored every legal move at a million
nodes. That gives a dense reward (the chosen move's win probability) next to the sparse one.

**The primer.** Seven generated task families: board reading, legal moves, the position after a
move, attacks and checks, best move, evaluation, best line. That's 1.3M examples and 192M tokens
for the "M" size, and a tenth of that for "S". About half the best-move examples are puzzle
positions answered with the puzzle's solution; the rest are positions from the Lichess evaluation
database answered with Stockfish's move. A contamination filter keeps every test position and
every test game out.

**Training.** SFT is a full fine-tune, one epoch. GRPO uses TRL with vLLM, LoRA rank 32, 200
steps of 64 prompts × 8 samples, on one spot A100. The prompt lists the legal moves and asks for
one move in `<answer>` tags.

**Evaluation.** Greedy, one answer per solver position, so a puzzle is solved only if every move
in it is right. 95% bootstrap CIs, and paired bootstraps for arm-vs-arm differences.

## Results

| | test2000 solve |
|---|---|
| Qwen3.5-2B zero-shot | 4.1% |
| GRPO from the base, dense / sparse | 25.8% / 28.0% |
| primer-M, SFT only | **35.7%** |
| primer-M → GRPO, sparse / dense | 35.4% / 32.6% |
| Stockfish at one node | 68.6% |

**GRPO from the base model reproduces the plateau.** The base model solves 4.1%. GRPO gets it
to about 25% within the first 25 steps, roughly $2 of GPU time, and then it flattens. 200 steps
end at 26–28% under either reward. I'd predicted about 10%, so the plateau came much faster and
higher than I expected, and right where Chess-R1 saw it.

**Sparse reward learned fine.** Chess-R1's 3B model got nothing from the binary reward. Mine
learned as fast as with the dense Stockfish reward and ended 2.2 points ahead of it. At the
start, about 6% of the base model's samples (temperature 1) hit the right move, so roughly a
third of the groups of eight have a correct sample to learn from, and that is enough. The dense reward added nothing measurable while both runs were
healthy.

**The primer raises the result after RL (H1 holds).** Primer → GRPO beats GRPO from the base by
**+7.4 points [+5.8, +9.2]** with the sparse reward and +6.8 [+5.2, +8.4] with the dense one.

**But RL adds nothing to the primer.** The primer alone scores 35.7%. Primer → GRPO sparse is
−0.2 points from it [−1.6, +1.1], and dense is −3.1. The dense loss turned out to be my fault:
the adaptive entropy bonus had a target of 0.2, tuned on the base model, and the primer model
starts at 0.11, so the bonus pushed it off its answers. With the target at the primer's own
entropy, it came back to −0.9, which is noise. pass@8 tells the same story: the primer samples a
right answer in 51% of dev puzzles within 8 tries, and after RL only 43–47%. RL narrowed the
distribution without finding anything new. That's what [Shen et al.](https://www.alphaxiv.org/abs/2607.16097)
describe as sharpening without discovery.

**More primer, higher score after RL (H3, three points).** None, S (19M tokens) and M (192M)
give 25.8%, 29.5% and 34.8% after RL, and each step is a paired difference whose CI excludes 0.
On the smaller primer, RL did add +4.0 points. So RL closes some of the gap from below, but
doesn't push past a strong start. I dropped the planned L size to stay in budget, so this is a
monotone curve, not a scaling law.

## The surprises

**Rules don't make tactics.** I built a rules-only primer with as many tokens as primer-M, all
board reading and legal moves, no move choice. It learned the rules: 99% on "what's on this
square", 94% on "what's the FEN after this move". After GRPO it solved 26.2%, +0.4 points over RL
with no primer at all. The primer's gain comes from its move-choice data, the puzzle solutions
and Stockfish's moves, not from knowing the board. That cuts against the knowledge story I
started with: the knowledge that mattered was "which move", not "what's where".

**The skill is narrower than the number.** Every prompt lists the legal moves. Drop the list and
the base model scores 0.1%, primer-M 1.7%, and primer → GRPO 1.9% after 200 more steps of RL
without the list. What the models learned is to pick the tactic out of 30-odd listed moves. My
prediction for this one was 28–36%, which made it my worst miss. The primer's best-move examples
always showed the list in the prompt, so this shows the primer depends on the list, not that a
primer trained without it would fail. That run is still open.

**The RL failures were plumbing, not chemistry.** The first GRPO config collapsed its entropy
within 25 steps, and by step 50, 74% of sample groups had identical rewards and gave no gradient. An
adaptive entropy bonus fixed that. Then about 1% of completions learned to close `</answer>`
and keep writing until the 1,024-token cap. The reward never read those tokens, so nothing
stopped them. In one run that share went from 1.6% to over 80% in 15 steps, and since the loss
averages over all tokens, the five answer tokens stopped getting any gradient and the answers
froze. Stopping generation at `</answer>` fixed that. Each fix became a new config version with
its own ADR, and the earlier runs stayed frozen so the comparisons stay clean.

**Predictions keep you honest.** I wrote 1-node Stockfish down at 30–45%. It scored 68.6%,
because `go nodes 1` still finishes a depth-1 search with quiescence. I wrote GRPO from the base
at about 10%, and it ended at 24%, most of it gained by step 25. I wrote the no-list primer at 29%, and it scored
1.7%. All of them sit in RESULTS.md next to the predictions, which is the point.

## Cost

**$197.74 of $600 in credits**, of which $190.68 was 61 hours of spot A100 time. That covered 14
finished training runs (3 SFT, 11 GRPO), 4 stopped ones and all the evals. The 23 preemptions
mostly cost a resume from the last checkpoint. A GRPO run cost $8–12, primer-M SFT $22, and the
full rules-only experiment $44, including two attempts that lost the answer format and one
preemption in the middle of a checkpoint save.

The budget machinery was built before any experiment code: a ledger, a launch gate that refuses
any job whose worst case could break a ceiling or outlive the credit, a sweep, and a Cloud
Function kill switch that detaches billing. The part that earned its keep was the gate:
it forced a worst-case number and an expiry check before every launch.

## Limitations

- One model (Qwen3.5-2B), one seed per arm. The CIs cover puzzle sampling, not training variance.
- Puzzles, not games. Nothing here measures playing strength, and the legal-move list is a big
  crutch.
- The primer's move-choice data includes puzzle solutions from the same distribution as the test
  set (different games, contamination-filtered). Part of "primer" is plain imitation of puzzle
  answers, which is why I report primer-only next to every RL arm.
- The Gemini baselines are still pending: they run on the second credit after 2026-11-13.

## Try it

The [puzzle browser](https://nikext.github.io/knight-school/) shows all 2,000 test puzzles with
every model's answer. You can filter to "the primer solved it, RL from the base didn't" or try a
puzzle yourself before you look. The code, configs, ledger and every eval file are on
[GitHub](https://github.com/nikext/knight-school), and the models and data are on Hugging Face.

---

## CV bullets

- Fine-tuned a 2B open LLM (Qwen3.5-2B) for chess puzzles with SFT and GRPO (TRL + vLLM, LoRA).
  A teacher-free primer (python-chess and Stockfish data, no LLM text) raised the post-RL solve
  rate from 28.0% to 35.4% (+7.4 points, 95% CI [+5.8, +9.2], n = 2,000), beyond the ~25–30%
  plateau reported by Chess-R1. Showed with a primer-only control that the gain came from the SFT,
  not the RL.
- Ran 18 training runs on spot GPUs for $197.74 total (of $600 in credits) under a self-built
  budget gate (ledger, worst-case pre-flight checks, sweep, billing kill switch). Every run is
  reproducible from the repo.
- Showed that the post-RL score rises with primer size (25.8% → 29.5% → 34.8%, none/S/M), that a
  rules-only primer adds nothing (+0.4 points), and that the skill depends on the legal-move list
  in the prompt (1.9% without it). Each prediction was written down before the run.
- Built and deployed a React puzzle browser for 2,000 test puzzles, comparing four model stages
  with filters by rating, theme and outcome.
