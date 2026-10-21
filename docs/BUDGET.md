# Budget: the rules for spending money

The user has two Google Cloud credits (read from Billing → Credits on
2026-10-21; details in ADR-013). This project must never cost them real money.
This file is the contract, `costs/caps.yaml` is its machine-readable form,
and `ks.cloud` enforces it in code.

## 1. Numbers

| Pool | Credit | Left (2026-10-21) | Expires | Ceiling | Usable |
|---|---|---|---|---|---|
| `compute` | Google Developer Program annual: all of Google Cloud | $440.94 | **2026-11-12** | **$360** | now → jobs must **end by 2026-11-10 00:00Z** |
| `vertex` | Marketing – GDP Premium Support 4: "certain usage", assumed Gemini only (unverified) | $209.26 | 2027-04-08 | **$180** | from **2026-11-13** (except the M0 smoke call) |

Each ceiling is `min(planned ceiling, 0.9 × remaining)`. The 10% reserve
absorbs billing lag, storage, egress and rounding, and nothing is ever planned
into it.

**The credits sit on the billing account, and other projects draw on them
too** (zuri-sunny, swiss-admin-navigator's Gemini evals, …). So:

- the user re-reads Billing → Credits **at least weekly**. The gate refuses
  to launch when the reading in caps.yaml is older than 7 days;
- the gate caps every job at `0.9 × remaining − our spend since the reading −
  running worst cases` (ADR-014), even when the ceiling would allow more.

**Why Gemini waits until 2026-11-13:** both credits may cover Vertex AI, and
the expiring one could be drawn first. That would quietly shrink the GPU
budget. After the annual credit is gone, Gemini can only draw on the
Marketing credit. The first post-expiry call is a 1-cent scope test; if the
next day's Billing → Reports shows it as net cost, the vertex pool goes to
$0 and Gemini baselines are dropped.

**After 2026-11-12, compute and storage are not covered** unless that test
shows otherwise. The bucket and registry are emptied by 2026-11-11 (M6
moves forward accordingly).

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

\* Dead: M0 found no evidence that the vertex credit covers Vertex AI custom
training (ADR-013), so this line stays unspent. Never invent Vertex spend to
use up credit. The vertex M2 line pays for Gemini baselines, which now run
after 2026-11-13.

A milestone may not exceed its line without the user approving the overrun
in chat. The overrun is booked against `contingency` in the ledger.

## 2. Prices (measured in M0)

Spot, whole VM (GPU + vCPU + RAM + bundled local SSD), from the Cloud Billing
Catalog API on 2026-10-21 (`ks prices`). The user checked the L4 machine
against the console. The boot disk adds $0.11/GB-month (200 GB ≈ $0.03/h).

| Machine | GPU | us-central1 $/h | europe-west4 $/h | Plan assumed | Use |
|---|---|---|---|---|---|
| `g2-standard-8` | 1× L4 24 GB | **0.511** | 0.538 | 0.30 | smoke tests, evals of ≤ 4B models, LoRA GRPO smoke |
| `a2-ultragpu-1g` | 1× A100 80 GB | **3.040** | 3.100 | 1.80 | main SFT and GRPO runs |
| `a3-highgpu-1g` | 1× H100 80 GB | **6.274** | 8.437 | 3.00 | only if measured $/step beats the A100 by > 2× (M3) |
| `e2-standard-2` | none | 0.040 | 0.044 | — | infra tests (kill switch) |

The real prices are 70% (L4, A100) and 109% (H100) above the third-party
figures this plan was written with. Spot prices can change up to once every
30 days, so the launcher refuses a `prices.yaml` that is unverified or older
than 30 days.

Rough job costs at the measured prices (M3 measures the real ones): a GRPO
run on a ~2B model is **$17–34** (was $10–20), a GRPO run on a ~4B model is
**$42–59** (was $25–35), and primer SFT of a 2B model on 150M tokens is
**$9–17** (was $5–10). The $360 compute ceiling buys at most ~118 A100-hours.
M3's re-plan will almost certainly cut M5. Gemini baselines are still about
$30–50 in total.

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
   - `--confirm` is present, which needs user approval;
   - plus the M0 additions (ADR-014): the credit window and expiry margin,
     a credit reading ≤ 7 days old with enough headroom, no other open
     attempt, and a fresh run id (or the next attempt number for a retry).
   It appends a `start` event to the ledger *before* creating the resource and
   labels everything `app=knight-school,run=<id>,milestone=<m>`.
4. **Teardown and sweep.** `make sweep` lists every labelled VM, disk, Vertex
   job and endpoint in the project, and `DELETE=1` removes them. It runs at the
   end of every session (CLAUDE.md).
5. **Budgets and kill switch (backstop).** Billing data lags by hours, so this
   layer catches slow leaks, not fast ones. There are three budgets on the
   project, all over a fixed period 2026-10-01 → 2027-04-30 (a monthly
   budget would reset on Nov 1), all publishing to Pub/Sub topic `ks-budget`:
   - `ks-total-gross`: all services, **credits excluded**, amount $540
     (= 360 + 180). Thresholds at 50, 75, 90 and 100%.
   - `ks-vertex-gross`: Vertex AI only, credits excluded, $180. Same
     thresholds.
   - `ks-net`: all services, **credits included**, $5. It fires the moment
     credits stop covering this project's usage, for example when another
     project used up the shared credit. Thresholds at 20% ($1) and 100%.

   The Cloud Run function `ks-killswitch` reads each message. At ≥ 90% of
   either gross budget, or ≥ $1 net, it deletes all `app=knight-school` VMs and
   cancels running Vertex custom jobs. The user opted in (M0), so at net ≥ $5
   it also detaches billing from the dedicated project `knight-school-nt26`.
   That stops everything. M0 tested the function with synthetic messages:
   19% did nothing, and 93% deleted the labelled test VM.
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
- No Gemini spend before 2026-11-13 except the M0 smoke call (ADR-013). The
  first call after that date is a 1-cent scope test.
- The harness computes cost from `usage_metadata` × `prices.yaml` after every
  call and aborts a run at its cap.
- For any run over $5, first do a 20-puzzle pilot, extrapolate the cost, and
  ask the user. Then submit the full run as a **batch** job, which is
  discounted (about 50%, verify in M2).
- Restrict thinking with the model's thinking setting, and record it in the
  report.
