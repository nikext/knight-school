# M6: Release and showcase

**Goal:** make the work visible and verifiable. That means models and data on
Hugging Face, a puzzle browser people can click through, a README that
leads with the results, a blog draft and CV bullets, and then a clean
teardown with a final cost line.

**Budget:** compute $9 · vertex $4. Mostly egress and a final eval or two.

**Read first:** RESULTS.md (all of it), README.md, GCP.md §8. Every step
that publishes something needs the user's yes (CLAUDE.md).

## Tasks

1. **Final reconcile.** Close the ledger and compare `make costs` with
   Billing → Reports (the user reads it). Explain any gap.
2. **Pick the released checkpoints.** The E3 primer → GRPO dense model, plus
   the best E5c ~4B model if it exists. Merge LoRA into the weights.
3. **Hugging Face** (ask; the user provides `HF_TOKEN`):
   - model repos with cards: base model and its license, training recipe,
     eval tables with CIs, the prompt format, limitations ("puzzle solve
     rate, not playing strength"), and a "no LLM-generated data" note;
   - a dataset repo with the eval sets, the `rl_train` reward tables, and the
     primer *generator config plus a sample*, with a CC0 note for the Lichess
     data. The full primer can be regenerated with `make data`.
4. **Puzzle browser** (`site/`, Vite + a board component, static):
   - about 200 test puzzles, stratified by rating;
   - for each: the board, the solution, and the outputs of base, primer and
     primer → GRPO, including their `<think>` text;
   - filters by rating bin and outcome.

   Precompute all the data; there is no live model. Deploy to GitHub Pages
   (ask).
5. **README rewrite:**
   - a one-paragraph pitch and the headline result sentence;
   - the dev-solve-vs-$ figure and the main results table (E1–E3, top rows);
   - the E4 curve;
   - "what I learned" (3–5 bullets, including anything that failed);
   - the cost table ("spent $X of $600 credits") and links to the docs, HF
     and the browser.
6. **`docs/BLOG.md` draft** (about 1,500 words): the question, why it's
   interesting (Chess-R1's plateau), the setup, the results with figures,
   surprises, cost breakdown, and limitations. The user decides where it's
   posted.
7. **CV bullets** (in the PR description and at the end of BLOG.md), filled
   with real numbers. Templates:
   - "Trained a 2B open LLM with GRPO (TRL + vLLM, LoRA) on Lichess
     puzzles. A teacher-free chess primer raised the post-RL solve rate from
     X% to Y% (n=2,000, 95% CI ±Z), beyond the ~25–30% plateau reported by
     Chess-R1."
   - "Ran 10+ training runs on spot GPUs for $X total under a self-built
     budget gate (ledger, pre-flight checks, kill switch); every run is
     reproducible from the repo."
   - "Showed that post-RL accuracy scales log-linearly with primer size
     (S/M/L) and that rules-only knowledge recovers N% of the gain." Adjust
     to what was actually found.
8. **Portfolio entry** in `~/Documents/GitHub/portfolio2`. That's another
   repo, so ask first and follow that repo's own CLAUDE.md.
9. **Teardown:** `make sweep DELETE=1` (it should already be empty), then
   delete old registry images, `scratch/` and optimizer states. Keep the
   budgets and kill switch until the project is deleted. Ask the user whether
   to delete the dedicated project now that everything is published. Put the
   final cost line in README.md and RESULTS.md.

## Done when

- The HF repos are live, with cards (if the user agreed), and the puzzle
  browser is deployed (if the user agreed).
- The README leads with the results and cost line, the blog draft and CV
  bullets are written, and the PLAN.md table is all ✅ or ⏭️ with reasons.
- `make sweep` is clean and the final ledger is reconciled and committed.
