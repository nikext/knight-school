# M0: Bootstrap and money guardrails

**Goal:** a working skeleton where money can't be spent by accident. CI is
green, the GCP project is ready, prices are real, the `ks.cloud` gate is
tested, budgets and the kill switch are live and tested, and one 15-minute L4
spot VM has run and deleted itself. **No experiment code in this milestone.**

**Budget:** compute $5 · vertex $1. Expected spend: well under $1.

**Read first:** `CLAUDE.md`, `docs/BUDGET.md` (all of it), `docs/GCP.md`,
and ADR-002 and ADR-003 in `docs/DECISIONS.md`.

## 1. Ask the user first (one message, then wait)

Use AskUserQuestion for the choices, then ask in plain text for the credit
details:

1. **GCP project:** a new dedicated `knight-school-<suffix>` (recommended,
   GCP.md §2) or the shared `random-projects-509513`.
2. **PR review:** the user reviews each milestone PR before merge, or you
   merge on green CI.
3. **Experiment tracking:** a public W&B project (nice for the portfolio,
   needs their account and key) or TensorBoard logs in GCS + CSVs committed
   to `results/`.
4. **Kill switch billing detach** at net ≥ $5: yes or no. Only offer "yes"
   with a dedicated project.
5. **Credits (free text):** ask the user to open Cloud console → Billing →
   Credits and paste, for each credit, its name, remaining value, expiry, and
   scope (services covered, excluded SKUs, project restrictions). From that,
   work out: does the compute credit cover Compute Engine spot GPUs? Does the
   Vertex credit cover Vertex AI custom training or only generative AI?

Record the answers in CLAUDE.md "Session-agreed settings" and in
`costs/caps.yaml → verified`. If remaining credit is below the stated
amount, **propose** new ceilings and allocations (`min(ceiling, 0.9 ×
remaining)`, scaled down proportionally). The user approves them, then you
edit caps.yaml. If a credit doesn't cover GPUs at all, stop and tell the
user. The plan doesn't work without that.

## 2. Repo tooling

- A uv project, Python 3.12, one package `ks/` with subpackages `chess`,
  `data`, `eval`, `train` and `cloud`, and a CLI entry point `ks` (typer or
  argparse).
- Base deps: python-chess, pyyaml, pydantic, polars or pyarrow, zstandard,
  google-cloud-storage, requests. Optional extras: `[train]` (torch, vllm,
  trl, peft; installed in the container, not in CI) and `[gemini]`
  (google-genai).
- Dev deps: ruff, pyright, pytest. `pre-commit` with ruff, ruff-format,
  end-of-file, trailing-whitespace, and a check that blocks `.env`, `*-key.json`
  and credential JSON.
- `Makefile`: `setup lint test costs reconcile sweep`, plus placeholders for
  `data eval` that later milestones fill in.
- `.github/workflows/ci.yml`: lint, typecheck and unit tests on PRs and main.
  No GCP access in CI.

## 3. GCP setup (ask before creating anything)

- If dedicated: `gcloud projects create`, then `gcloud billing projects link`
  to the user's billing account (look it up read-only with
  `gcloud billing accounts list`; don't commit its id). Write `.env`.
- `infra/setup.sh` (idempotent, `DRY_RUN=1`): APIs, bucket plus lifecycle
  rules, Artifact Registry repo plus cleanup policy, and the SAs `ks-runner@`
  and `ks-killswitch@` with their roles (GCP.md §4). Run it with DRY_RUN
  first, show the user, then run it for real.
- **Quotas:** request GPU quota **1** (GCP.md §4). Approval can take a while,
  so do it early in the session. Record the request ids and their status in
  the PR.
- **Vertex smoke:** one tiny Gemini call with ADC (a few tokens, < $0.01).
  Log it as a ledger `charge`.

## 4. Prices

- `ks prices` fetches spot SKUs from the Cloud Billing Catalog API (GCP.md §6)
  for `g2-standard-8`, `a2-ultragpu-1g` and `a3-highgpu-1g` in us-central1 and
  europe-west4. If the Vertex credit covers training, also fetch the Vertex
  training spot SKUs. It writes `costs/prices.yaml`.
- Unit tests for the SKU-to-machine-price assembly, using a saved fixture of
  the API response.
- Show the user the numbers next to the pricing calculator for one machine.
  Set `verified: true` once they agree. Update BUDGET.md §2 with the real
  prices. If they differ from the assumptions by more than 25%, recompute the
  "rough job costs" line.

## 5. The gate: `ks.cloud`

Implement BUDGET.md §3–4 exactly:

- `ledger.py`: append events, fold them into per-pool and per-milestone
  totals, plus the worst case of running jobs.
- `gate.py`: pure function `check(run_config, caps, prices, ledger) -> Ok |
  Refusal(reason)`. **This is the most important code in M0.** Unit-test
  every rule:
  - over the pool ceiling;
  - over the milestone allocation, with and without contingency;
  - running jobs' worst case counted;
  - prices unverified or stale;
  - more than 1 GPU;
  - not spot;
  - `max_hours > 24`;
  - `--confirm` missing;
  - allocations that don't sum to the ceiling (reject caps.yaml);
  - a preemption retry that would break `run_budget_usd`.
- `launch.py`: the GCE backend per GCP.md §5 (`infra/vm_startup.sh`
  included). Add the Vertex backend only if the Vertex credit covers
  training; otherwise leave a stub that raises a clear error.
- `watch.py`: poll the run's markers every 5 min, detect preemption,
  relaunch (respecting the gate), and stop at `run_budget_usd`. It will
  usually run under Claude Code's Monitor or `run_in_background`.
- `reconcile.py`: close finished attempts with their real hours (GCS
  markers; otherwise the VM's deletion time from the audit log; otherwise
  `max_hours` as the conservative fallback).
- `sweep.py`: GCP.md §8.
- `ks costs` prints, per pool, the ceiling, spent, running worst case and
  remaining, then per-milestone allocation vs spent.

## 6. Budgets and kill switch (ask before deploying)

- `infra/budgets.sh`: the three budgets (BUDGET.md §3.5, GCP.md §7). First
  verify the Vertex AI billing service id with the Catalog API's
  `/v1/services`.
- `infra/killswitch/`: the function, unit tests for its decision logic, and
  a deploy script.
- **Test:** create a labelled `e2-micro`, publish a synthetic over-threshold
  message, and confirm the VM is deleted and the decision logged. Also
  publish an under-threshold message and confirm nothing happens.
- Tell the user the budgets also email the billing admins, and what each
  alert means.

## 7. Smoke run

- `configs/runs/m0-smoke-l4.yaml`: `g2-standard-8`, `max_hours: 0.25`, image
  `nvidia/cuda:<pinned>-base` (our own image comes in M2), command
  `nvidia-smi && sleep 120`.
- Show the gate output, ask, then `ks launch … --confirm --watch`. Confirm
  that the VM wrote its markers, deleted itself, and that `ks reconcile`
  closed the entry with its actual cost (expect about $0.05–0.10). Confirm
  `make sweep` shows nothing.
- If the L4 quota isn't approved yet, finish everything else and note "smoke
  pending quota" under M0's status row. M1 runs on the laptop and doesn't
  need it. M2 must not start cloud work until the smoke has passed.

## Done when

- `make lint test` passes locally and in CI, with ≥ 15 gate tests.
- `costs/prices.yaml` is verified, and the caps reflect the user's real
  remaining credits.
- `gcloud billing budgets list` shows the three `ks-` budgets, and the kill
  switch test passed (log line in the PR).
- The smoke VM ran and deleted itself, the ledger has its start and end, and
  `make sweep` is clean. Or the smoke is explicitly pending quota, with a
  note.
- CLAUDE.md settings and commands are filled in, the PLAN.md row is updated,
  and the PR has the `make costs` output.
