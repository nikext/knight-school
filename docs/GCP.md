# Google Cloud: project, quotas, launch backends, kill switch, teardown

## 1. Ground rules

- **The user runs** `gcloud auth login` and
  `gcloud auth application-default login` themselves (suggest
  `! gcloud auth login`). gcloud is at `~/google-cloud-sdk/bin/gcloud`.
- **Read-only calls are fine** (`list`, `describe`, Catalog API). Anything
  that creates a resource needs the user's yes. Anything with a GPU goes
  through `ks launch` (BUDGET.md §3).
- **Label everything** `app=knight-school`. Runs add `run=<id>` and
  `milestone=<m>`. Names are prefixed `ks-`.
- Never commit keys. Locally, use ADC. VMs and jobs run as `ks-runner@`.

## 2. Project

**Recommended: a new dedicated project**, e.g. `knight-school-<suffix>`,
linked to the user's existing billing account. Reasons:

- The budgets can filter on one project, with no other app's spend mixed in.
- The kill switch may detach billing at the net-spend trigger (BUDGET.md §3.5)
  without taking down zuri-sunny or swiss-nav.
- Final teardown can be "delete the project".

The alternative is the shared `random-projects-509513`. Everything still
works, but the net budget and the billing-detach option must then be
disabled. The user chooses in M0. Record the choice in CLAUDE.md
"Session-agreed settings".

**Credits:** one billing account (USD) holds the credits and is shared by all
the user's projects. Check in M0 that the credits apply to this project.
Some promotional credits are project-scoped.

## 3. Region

- **us-central1** for GPUs, the bucket and the registry. It has the widest
  spot GPU availability and the lowest prices (ADR-009).
- **europe-west4** is the fallback region for stockouts. The watcher may move
  a run there, but only if the run's inputs are mirrored (a cross-region
  copy of a few GB costs cents; log it).
- europe-west6 (Zürich) isn't used. It offers few GPU types.

## 4. One-time setup (`infra/setup.sh`, idempotent, `DRY_RUN=1` supported)

- **APIs:** compute, storage, artifactregistry, cloudbuild, aiplatform,
  cloudbilling, billingbudgets, pubsub, run, cloudfunctions, eventarc,
  logging, iam, cloudquotas (verify names with `gcloud services list
  --available`).
- **Bucket:** `gs://<project>-knight-school`, us-central1, uniform access,
  public access prevention on. Layout: `data/<version>/`, `runs/<id>/`,
  `scratch/`. Lifecycle rules: delete `scratch/` objects after 14 days, and
  delete noncurrent versions after 7 days (if versioning is on, it is off by
  default).
- **Artifact Registry:** `knight-school` (docker, us-central1). Keep only
  the last 3 tags via a cleanup policy.
- **Service accounts:**

| SA | Used by | Roles |
|---|---|---|
| `ks-runner@` | training/eval VMs and Vertex jobs | `storage.objectAdmin` on the bucket, `artifactregistry.reader`, `logging.logWriter`, `compute.instanceAdmin.v1` (so a VM can delete itself; a dedicated project keeps this contained), `aiplatform.user` (Gemini calls from eval jobs, if any) |
| `ks-killswitch@` | kill-switch function | `compute.instanceAdmin.v1`, `aiplatform.user` (cancel custom jobs), and only with the opt-in, billing detach per Google's "disable billing with notifications" guide (verify the minimal role) |

- **Quotas** (request in M0, as approval can take hours or days): set
  `GPUS_ALL_REGIONS` to 1, and 1 each for the spot (preemptible) L4, A100 80 GB
  and H100 quotas in us-central1 (and europe-west4 for fallback). Use the
  console (IAM & Admin → Quotas) or `gcloud beta quotas preferences create`
  (verify the quota IDs). If the Vertex credit covers training, also request
  the Vertex custom-training spot GPU quotas at 1. **Never more than 1.** The
  quota is the burn-rate cap (BUDGET.md §3.1).

## 5. Launch backends (`ks.cloud.launch`)

### GCE spot VM (default)

```bash
gcloud compute instances create ks-<run-id>-a<attempt> \
  --zone=<zone> --machine-type=<machine> \
  --provisioning-model=SPOT --instance-termination-action=DELETE \
  --max-run-duration=<max_hours>h --maintenance-policy=TERMINATE \
  --no-restart-on-failure \
  --image-family=<DLVM family with NVIDIA driver + docker> --image-project=deeplearning-platform-release \
  --boot-disk-size=200GB --boot-disk-type=pd-balanced \
  --service-account=ks-runner@<project>.iam.gserviceaccount.com --scopes=cloud-platform \
  --labels=app=knight-school,run=<run-id>,milestone=<m> \
  --metadata-from-file=startup-script=infra/vm_startup.sh \
  --metadata=ks-run-id=<run-id>,ks-image=<image>,ks-command=<b64>,ks-max-seconds=<n>
```

- `ks launch` builds this command. It is never typed by hand.
- Verify the current Deep Learning VM image family names with
  `gcloud compute images list --project deeplearning-platform-release`.
- **`infra/vm_startup.sh`:**
  1. Write `runs/<id>/attempts/<n>/started` to GCS.
  2. `docker pull` the image.
  3. `timeout --signal=TERM <max_seconds − 600> docker run --gpus all …`.
  4. Sync the outputs.
  5. Write `ended` with the exit code.
  6. Delete the VM: `gcloud compute instances delete $(hostname) --zone … --quiet`.

  Use `trap` so step 6 runs on errors too. `max-run-duration` is the backstop
  if the script itself dies.
- **Stockouts:** try each zone in the run config, then the fallback region.
  Log every attempt.

### Vertex AI custom job (only if the Vertex credit covers training)

A `CustomJob` with one worker pool: `machineSpec` (same machine, one
accelerator), `containerSpec` (same image and command),
`scheduling.strategy = SPOT`, `scheduling.timeout = <max_hours>h`, labels, and
`serviceAccount = ks-runner@`. Vertex tears the machine down itself when the
job ends. Pricing is the Compute Engine spot rate plus Vertex's management
fee (verify on the Vertex pricing page). Put it in `prices.yaml →
vertex_training_spot`. Check how Vertex handles spot preemption (restart vs
fail) and set the watcher accordingly.

## 6. Prices (`ks prices`)

Fetch SKUs from the Cloud Billing Catalog API using a gcloud access token:
`GET https://cloudbilling.googleapis.com/v1/services/<service-id>/skus?currencyCode=USD`.
Compute Engine is `6F81-5844-456A` and Vertex AI is `C7E2-9256-1C43`
(verify both via `/v1/services`). For each machine, add up the spot GPU SKU
and the spot vCPU and RAM SKUs × the machine's shape (get the shape from
`gcloud compute machine-types describe`). Write `costs/prices.yaml` with
`fetched_on`. Set `verified: true` only after the user has cross-checked one
machine against the console pricing calculator.

## 7. Budgets and kill switch (`infra/budgets.sh`, `infra/killswitch/`)

- Pub/Sub topic `ks-budget`.
- Three budgets (BUDGET.md §3.5), each with `--filter-projects`, thresholds,
  and `--notifications-rule-pubsub-topic=projects/<p>/topics/ks-budget`:
  - `ks-total-gross`: `--credit-types-treatment=exclude-all-credits`,
    $540.
  - `ks-vertex-gross`: also `--filter-services=services/C7E2-9256-1C43`,
    $180.
  - `ks-net`: `--credit-types-treatment=include-all-credits`, $5.

  These flags were checked in gcloud 586 on 2026-10-21. Budgets publish
  several times a day, not only when a threshold is crossed, so the function
  computes `costAmount / budgetAmount` itself.
- **Function `ks-killswitch`** (Cloud Run functions, Python, Pub/Sub
  trigger):
  1. Parse the message.
  2. Decide on the rule (≥ 90% of a gross budget, or ≥ $1 net).
  3. Delete `labels.app=knight-school` instances in all zones.
  4. Cancel running Vertex custom jobs with the label.
  5. With the opt-in and net ≥ $5, detach billing.
  6. Log a structured line.

  It is idempotent and has unit tests for the decision logic.
- **Test in M0:** create a labelled `e2-micro` (about a cent), publish a
  synthetic message over the threshold to `ks-budget`, and check the VM is
  gone and the function logged the decision.

## 8. Sweep and teardown

- `make sweep` lists labelled instances (all zones), disks,
  RUNNING/PENDING Vertex custom jobs, any Vertex endpoints, and Workbench
  instances. `DELETE=1` deletes them after printing them.
- **Final teardown (M6):** delete old registry images, `scratch/`, and
  optimizer states. Keep the final models in Hugging Face and the eval
  outputs in the repo. Keep the budgets and kill switch until the project is
  deleted. Whether to delete the dedicated project is the user's call.
