# Budget: the rules for spending money

The user has **$400 of GCP credit** and **$200 of Vertex AI credit** (stated
2026-10-21). This project must never cost them real money. This file is the
contract, `costs/caps.yaml` is its machine-readable form, and `ks.cloud`
enforces it in code.

## 1. Numbers

| Pool | Covers (billing services) | Credit | Ceiling | Untouchable reserve |
|---|---|---|---|---|
| `compute` | Compute Engine, Cloud Storage, Artifact Registry, Cloud Build, Pub/Sub, Cloud Run functions, networking | $400 | **$360** | $40 |
| `vertex` | Vertex AI: Gemini calls, and custom training **only if the credit covers it** | $200 | **$180** | $20 |

The reserve absorbs billing lag, storage, egress and rounding. Nothing is ever
planned into it.

**The credits sit on the billing account, and other projects draw on them
too** (zuri-sunny, swiss-admin-navigator's Gemini evals, …). In M0 the user
reads Billing → Credits and reports, for each credit: remaining amount, expiry
date, and scope (which services, and any excluded SKUs such as GPUs or Spot).
Each ceiling then becomes `min(ceiling, 0.9 × remaining)`, and the user
writes it into `costs/caps.yaml`.

### Allocation per milestone (USD)

| Milestone | compute | vertex | Pays for |
|---|---|---|---|
| M0 | 5 | 1 | 15-min L4 smoke VM, kill-switch function, storage |
| M1 | 1 | 0 | GCS storage for datasets (Stockfish runs on the laptop) |
| M2 | 15 | 50 | container build, model screening and baselines on a spot L4, GRPO compatibility smoke; Gemini baselines in batch mode |
| M3 | 70 | 0 | L4 smoke, A100-vs-H100 throughput test, 2 GRPO runs (E2), evals |
| M4 | 100 | 0 | primer SFT, 2 GRPO runs, evals (E3) |
| M5 | 110 | 110* | E4 and E5 in priority order, stopping when the line runs out |
| M6 | 9 | 4 | final evals, upload egress, teardown |
| contingency | 50 | 15 | only with explicit user approval in chat |
| **Total** | **360** | **180** | |

\* The vertex M5 line exists only if M0 confirms the Vertex credit covers
Vertex AI custom training. If it doesn't, the line stays unspent. Never invent
Vertex spend to use up credit.

A milestone may not exceed its line without the user approving the overrun
in chat. The overrun is booked against `contingency` in the ledger.

## 2. Price assumptions (verify in M0)

Spot, us-central1, whole VM (GPU + vCPU + RAM; disk is extra and small). These
are third-party figures from 2026-10 and **unverified**:

| Machine | GPU | ≈ spot $/h | Use |
|---|---|---|---|
| `g2-standard-8` | 1× L4 24 GB | 0.30 | smoke tests, evals of ≤ 4B models, LoRA GRPO smoke |
| `a2-ultragpu-1g` | 1× A100 80 GB | 1.80 | main SFT and GRPO runs |
| `a3-highgpu-1g` | 1× H100 80 GB | 3.00 | only if measured $/step beats the A100 (M3) |

On-demand prices are about 3× higher, which is one reason they are banned.
M0 replaces these with real numbers from the Cloud Billing Catalog API in
`costs/prices.yaml`. **The launcher refuses to run while that file says
`verified: false`.**

Rough job costs at these prices, to sanity-check plans (M3 measures the real
ones): a GRPO run on a ~2B model is $10–20, a GRPO run on a ~4B model is
$25–35, and primer SFT of a 2B model on 150M tokens is $5–10. Gemini
baselines are $30–50 in total, with Pro restricted to a 500-puzzle subset.

## 3. Guardrails, outermost first

1. **Burn-rate cap via quota.** The project's GPU quota is 1
   (`GPUS_ALL_REGIONS = 1`, and 1 per spot GPU type). The most it can burn is
   about one H100 at $3/h. This is the one limit that holds even if every
   other layer fails.
2. **Every job has a hard end.** GCE VMs are created with
   `--provisioning-model=SPOT --max-run-duration=<max_hours>h
   --instance-termination-action=DELETE`. Vertex custom jobs get
   `scheduling.timeout` and the SPOT strategy. The launcher refuses
   `max_hours > 24`. Inside the VM, the job also runs under `timeout`, and the
   VM deletes itself when the job ends (GCP.md §5).
3. **Pre-flight gate (`ks launch`).** Before creating anything it computes
   `worst_case = max_hours × hourly_price × 1.05` and refuses unless all of
   these hold:
   - `prices.yaml` is verified and less than 30 days old;
   - `pool_spent + pool_running_worst_case + worst_case ≤ pool ceiling`;
   - `milestone_spent + worst_case ≤ milestone allocation`, or
     `--use-contingency` is given, which needs user approval;
   - the machine has exactly 1 GPU and is spot;
   - `--confirm` is present, which needs user approval.
   It appends a `start` event to the ledger *before* creating the resource and
   labels everything `app=knight-school,run=<id>,milestone=<m>`.
4. **Teardown and sweep.** `make sweep` lists every labelled VM, disk, Vertex
   job and endpoint in the project, and `DELETE=1` removes them. It runs at the
   end of every session (CLAUDE.md).
5. **Budgets and kill switch (backstop).** Billing data lags by hours, so this
   layer catches slow leaks, not fast ones. There are three budgets on the
   project, all publishing to Pub/Sub topic `ks-budget`:
   - `ks-total-gross`: all services, **credits excluded**, amount $540
     (= 360 + 180). Thresholds at 50, 75, 90 and 100%.
   - `ks-vertex-gross`: Vertex AI only, credits excluded, $180. Same
     thresholds.
   - `ks-net`: all services, **credits included**, $5. It fires the moment
     credits stop covering this project's usage, for example when another
     project used up the shared credit. Thresholds at 20% ($1) and 100%.

   The Cloud Run function `ks-killswitch` reads each message. At ≥ 90% of
   either gross budget, or ≥ $1 net, it deletes all `app=knight-school` VMs and
   cancels running Vertex custom jobs. If the user opted in, at net ≥ $5 it
   also detaches billing from the project. That stops everything, so only do
   it on a dedicated project. M0 tests the function with a synthetic message.
6. **Reconciliation.** `make reconcile` closes ledger runs with their actual
   duration (from the run's GCS markers, or the VM's deletion time from the
   audit log). At the end of each milestone, the user compares `make costs`
   with Billing → Reports. Investigate any gap above $2 before the next launch.

## 4. Ledger

`costs/ledger.jsonl` is append-only, holds one event per line, and is
committed. `make costs` folds the events into totals.

```json
{"ts":"2026-10-25T09:12:00Z","event":"start","id":"m3-e2-dense-r1","milestone":"M3","pool":"compute","kind":"gce-spot","machine":"a2-ultragpu-1g","zone":"us-central1-a","max_hours":12,"price_per_hour":1.80,"worst_case_usd":22.68,"approved":"user, in session 2026-10-25"}
{"ts":"2026-10-25T19:40:00Z","event":"end","id":"m3-e2-dense-r1","hours":10.47,"actual_usd":18.85,"status":"done","source":"gcs-marker"}
{"ts":"2026-10-25T21:00:00Z","event":"charge","id":"m2-gemini-flash-test","milestone":"M2","pool":"vertex","kind":"gemini-batch","actual_usd":11.20,"tokens_in":810000,"tokens_out":2900000}
{"ts":"2026-10-31T12:00:00Z","event":"charge","id":"storage-2026-10","milestone":"M3","pool":"compute","kind":"storage","actual_usd":0.85}
```

A preempted run that the watcher restarts gets a new `start` event with the
same `id` and an `attempt` number. The user's approval covers the run's
approved total, not just one attempt.

## 5. Never allowed without the user asking for it

On-demand GPUs, multi-GPU machines, TPUs, reservations or committed-use
discounts, GKE, Vertex or Model Garden endpoint deploys (they bill per hour
while idle), Workbench notebooks, GPU quota above 1, large BigQuery scans,
cross-continent egress of checkpoints, and any spend whose purpose is to use
up credit.

## 6. Gemini spend (vertex pool)

- Gemini is only a **baseline**. It never generates training data (ADR-008).
- The harness computes cost from `usage_metadata` × `prices.yaml` after every
  call and aborts a run at its cap.
- For any run over $5, first do a 20-puzzle pilot, extrapolate the cost, and
  ask the user. Then submit the full run as a **batch** job, which is
  discounted (about 50%, verify in M2).
- Restrict thinking with the model's thinking setting, and record it in the
  report.
