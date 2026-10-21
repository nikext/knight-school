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

**Chosen in M0: the dedicated project `knight-school-nt26`**, linked to the
user's billing account on 2026-10-21. The account allows 5 linked projects;
to free a slot the user had billing unlinked from `empl-mngmt` (its one Cloud
Run service was already failing). Reasons for a dedicated project:

- The budgets can filter on one project, with no other app's spend mixed in.
- The kill switch may detach billing at the net-spend trigger (BUDGET.md §3.5)
  without taking down zuri-sunny or swiss-nav.
- Final teardown can be "delete the project".

The alternative is the shared `random-projects-509513`. Everything still
works, but the net budget and the billing-detach option must then be
disabled. The user chooses in M0. Record the choice in CLAUDE.md
"Session-agreed settings".

**Credits:** one billing account (USD) holds the credits and is shared by all
the user's projects. Neither credit is project-scoped. The annual one covers
all of Google Cloud and expires 2026-11-12 (BUDGET.md §1, ADR-013).

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
- **Service accounts** (created by `infra/setup.sh` in M0):

| SA | Used by | Roles |
|---|---|---|
| `ks-runner@` | training/eval VMs and Vertex jobs | `storage.objectAdmin` on the bucket, `artifactregistry.reader`, `logging.logWriter`, `compute.instanceAdmin.v1` (so a VM can delete itself; a dedicated project keeps this contained), `aiplatform.user` (Gemini calls from eval jobs, if any) |
| `ks-killswitch@` | kill-switch function | `compute.instanceAdmin.v1`, `aiplatform.user` (cancel custom jobs), `logging.logWriter`, and for the billing detach (opted in) `billing.projectManager` on the project, the minimal role that can unlink the project's billing account. It also has `run.invoker` on the function, because the Eventarc trigger calls it as this SA. |

- **Quotas.** All requested and **approved at 1** on 2026-10-21 within
  minutes: `GPUS-ALL-REGIONS-per-project` (it was 0) and
  `PREEMPTIBLE-NVIDIA-{A100-80GB,H100}-GPUS-per-project-region` in
  us-central1 and europe-west4. Spot L4 was already 1 in both regions. They
  were requested as quota preferences through the Cloud Quotas REST API
  (`POST /v1/projects/<p>/locations/global/quotaPreferences`), because
  `gcloud beta` isn't installed. Original plan: set
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
- Image: `common-cu129-ubuntu-2404-nvidia-580` (Deep Learning VM, NVIDIA
  driver 580, CUDA 12.9; checked 2026-10-21). It has **no Docker**: the
  first M0 smoke failed with `docker: No such file or directory`. The
  NVIDIA container toolkit (1.19.1) is there. So `vm_startup.sh` installs
  `docker.io` from Ubuntu when it's missing (24 s in the M0 smoke: Docker
  29.1.3), configures the NVIDIA runtime, and logs both versions. If the
  toolkit is ever missing, it installs that from NVIDIA's apt repo too. It's the default in
  `RunConfig.vm_image_family`. CPU-only test VMs use `debian-12` with
  `image: host`, which runs the command on the VM without Docker.
- `infra/vm_shutdown.sh` runs in the ~30 s GCE gives on deletion. It writes
  a `preempted` marker (if metadata says so) or `shutdown`, unless `ended`
  already exists. Only `preempted` makes the watcher retry.
- The job gets `max_hours` minus a reserve of min(10 min, a third) for
  syncing outputs and self-deleting.
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
(both verified via `/v1/services` on 2026-10-21). SKU names as of then:
`Nvidia L4 GPU attached to Spot Preemptible VMs running in <region>`,
`Spot Preemptible G2 Instance Core|Ram running in <region>` (A2, A3 and E2
alike), and `SSD backed Local Storage attached to Spot Preemptible VMs`.
A2 Ultra and A3 machines bundle 375 GiB of local SSD per partition (1 and 2
partitions), which is billed and included in the price. For each machine, add up the spot GPU SKU
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

  All three use a fixed period, `--start-date=2026-10-01
  --end-date=2027-04-30`. A calendar-month budget would reset on Nov 1.
  The flags were checked in gcloud 586 on 2026-10-21. Budgets publish
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
- **Deployed in M0** by `infra/killswitch/deploy.sh`: gen2, python312,
  internal-only ingress, max 1 instance, `KS_DETACH_BILLING=1`.
- **Tested in M0** (`infra/killswitch/test.sh`): a labelled `e2-standard-2`
  spot VM (`ks launch configs/runs/m0-killswitch-test.yaml`, $0.003). A 19%
  message did nothing; a 93% message deleted it within ~90 s. Logged:
  `"actions": ["delete us-central1-a/ks-m0-killswitch-test-a1: ok"]`.

## 8. Sweep and teardown

- `make sweep` lists **every** instance and disk in the project (it's
  dedicated), RUNNING/PENDING/QUEUED Vertex custom jobs, Vertex endpoints,
  and Workbench instances in our regions. Anything without
  `app=knight-school` is flagged UNEXPECTED: stop and tell the user.
  `DELETE=1` deletes only our own resources.
- **Final teardown (M6):** delete old registry images, `scratch/`, and
  optimizer states. Keep the final models in Hugging Face and the eval
  outputs in the repo. Keep the budgets and kill switch until the project is
  deleted. Whether to delete the dedicated project is the user's call.
