# M2: Eval harness, model choice, baselines (E0, E1)

**Goal:** a trustworthy measuring stick and a chosen main model. By the end,
`make eval` works for open models (laptop and cloud), Gemini, Stockfish and
random. The container image exists. ADR-011 is accepted with a model, and
the E0 and E1 tables in RESULTS.md are filled in.

**Budget:** compute $15 · vertex $50. Every cloud job goes through
`ks launch` and is asked for. Gemini runs go pilot → ask → batch.

**Calendar (ADR-013):** GPU jobs must end by 2026-11-10 00:00Z, and M3–M5
still need that window, so keep M2 to a few days. **No Gemini calls before
2026-11-13.** The vertex pool is locked until then, so M2 builds and tests
the Gemini backend and cost meter but does not run them (task 9). Spot
prices are ~70% above the old plan (BUDGET.md §2).

**Read first:** `docs/EVALS.md`, TRAINING.md §1–3 and §8, BUDGET.md §6,
RESEARCH.md §2. Check that M0's smoke run passed. If it's "pending quota",
finish it first.

## Tasks

1. **`ks.chess`:** `prompt.py` (TRAINING.md §2), `parse.py` (the answer
   parser and its tolerance rules) and `rewards.py` (TRAINING.md §3, reading
   the M1 reward tables). These are shared by eval and RL, so test them
   heavily. Freeze the prompt in M2 and record its hash.
2. **`ks.eval`:**
   - the harness and its four backends (EVALS.md §3);
   - metrics, the bootstrap and paired bootstrap, the puzzle-rating
     logistic fit, the per-bin table, and the report writer;
   - the cost meter and the `--max-usd` cap.

   Unit-test the metrics on synthetic outputs where the answers are known
   (perfect, all illegal, the 50% rating crossing).
3. **Container** (TRAINING.md §8). A Dockerfile on a pinned
   `vllm/vllm-openai` image, with TRL, PEFT and this package added. Check
   TRL's supported vLLM range and pin torch, vLLM and TRL together (ADR-004).
   Build and push `train:<sha>`, using Cloud Build if its free tier covers it
   (verify), otherwise a local podman build. Add an eval entry point that
   reads a model profile and a set from GCS and writes reports back.
4. **Model profiles** `configs/models/*.yaml` for the candidates in
   TRAINING.md §1. First verify the exact HF repo names, licenses, and
   whether each one has a text-only path in vLLM and TRL. Drop any candidate
   that needs hacks, and note why.
5. **Screening on dev500**:
   - ≤ 2B candidates on the laptop if they fit in 6 GB; otherwise everything
     in one spot L4 eval job (ask; ≈ $1–2).
   - Measure the legal-and-formatted rate, move accuracy, solve rate and
     prompt tokens.
   - Decide the thinking mode (native vs `<think>`) and record it in an ADR.
6. **GRPO compatibility smoke:** 5 TRL GRPO steps with LoRA and vLLM
   colocate for the top 2 candidates, using dummy rewards from `ks.chess.rewards`,
   in one L4 job (ask; ≈ $0.50). This only checks that the stack runs;
   tuning is M3's job.
7. **Choose the main model.** Accept ADR-011 with the screening table and
   the reasons. Count primer-S and primer-M tokens with its tokenizer and
   update the manifests and DATA.md §7.
8. **E0:** the probe500 harness mode (EVALS.md §4). Run it for the chosen
   base model.
9. **E1** (EVALS.md §5). Random and Stockfish (1 node, 1k nodes) on test2000
   (laptop). The chosen base model zero-shot on test2000 (laptop or L4).
   **Gemini (build now, run after 2026-11-13):**
   - list the current GA model ids on Vertex (Flash-Lite, Flash, Pro). On
     2026-10-21 the GA list included gemini-2.5-flash-lite/flash/pro and
     gemini-3.x flash models; re-check;
   - put live prices into `prices.yaml → gemini` (Catalog API, Vertex
     service `C7E2-9256-1C43`; e.g. 2.5 Flash Lite was $0.10/M in and
     $0.40/M out);
   - the cost meter refuses calls before the vertex pool's `usable_from`;
   - unit-test the backend with recorded responses, with no live calls in M2.

   **In the first session on or after 2026-11-13:** a 1-cent scope test.
   The next day, the user checks Billing → Reports that it was covered by
   credit (net $0). If it shows net cost, the vertex pool goes to $0 and the
   Gemini rows are dropped with a note. Otherwise: a 20-puzzle pilot per
   model, extrapolate, ask the user with the numbers, then batch jobs
   (Flash-Lite and Flash on test2000, Pro on test500), with a ledger
   `charge` per job. Stay inside $50. If the extrapolation says Pro won't
   fit, drop Pro to test-200 or skip it, and note that.
10. **Write up:** the E0 and E1 tables in RESULTS.md, and short notes on what
    stands out (legal rate, per-bin shape, how Gemini compares with Chess-R1's
    numbers).

## Done when

- The harness tests are green. The reports for every E1 row are committed under
  `results/eval/`.
- ADR-011 is accepted, `configs/models/<main>.yaml` exists, and the image is
  pushed with its digest recorded.
- The E0 base row and the E1 table are in RESULTS.md. The Gemini rows are
  marked "pending (after 2026-11-13, ADR-013)" and get their own small PR
  later.
- Spend is ≤ $15 compute and ≤ $50 vertex, the ledger is reconciled,
  `make sweep` is clean, the PLAN.md row is updated, and the PR has the
  `make costs` output.
