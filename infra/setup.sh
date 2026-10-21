#!/usr/bin/env bash
# One-time project setup (GCP.md §4). Idempotent: re-running only creates
# what is missing. DRY_RUN=1 prints every mutating command instead of running it.
#
#   DRY_RUN=1 infra/setup.sh     # show the plan
#   infra/setup.sh               # apply it
#
# Creates nothing billable by the hour: APIs, one bucket, one Artifact
# Registry repo, two service accounts and their IAM bindings.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a

: "${GOOGLE_CLOUD_PROJECT:?set in .env}"
: "${REGION:?set in .env}"
: "${BUCKET:?set in .env}"
: "${AR_REPO:?set in .env}"

GCLOUD="${GCLOUD:-$HOME/google-cloud-sdk/bin/gcloud}"
# A describe on a disabled API otherwise hangs on an "enable it?" prompt.
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
P="$GOOGLE_CLOUD_PROJECT"
DRY_RUN="${DRY_RUN:-0}"
LABELS="app=knight-school"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else
    printf '+'; printf ' %q' "$@"; printf '\n'
    "$@"
  fi
}

exists() { "$@" >/dev/null 2>&1; }

echo "== project: $P  region: $REGION  dry-run: $DRY_RUN"

# --- APIs -------------------------------------------------------------------
APIS=(
  compute.googleapis.com
  storage.googleapis.com
  artifactregistry.googleapis.com
  cloudbuild.googleapis.com
  aiplatform.googleapis.com
  cloudbilling.googleapis.com
  billingbudgets.googleapis.com
  pubsub.googleapis.com
  run.googleapis.com
  cloudfunctions.googleapis.com
  eventarc.googleapis.com
  logging.googleapis.com
  iam.googleapis.com
  cloudquotas.googleapis.com
  cloudresourcemanager.googleapis.com
)
enabled="$("$GCLOUD" services list --enabled --project="$P" --format='value(config.name)' 2>/dev/null || true)"
missing=()
for api in "${APIS[@]}"; do
  grep -qx "$api" <<<"$enabled" || missing+=("$api")
done
if ((${#missing[@]})); then
  run "$GCLOUD" services enable "${missing[@]}" --project="$P"
else
  echo "APIs: all enabled"
fi

# --- Bucket -----------------------------------------------------------------
if exists "$GCLOUD" storage buckets describe "$BUCKET" --project="$P"; then
  echo "bucket: $BUCKET exists"
else
  run "$GCLOUD" storage buckets create "$BUCKET" --project="$P" \
    --location="$REGION" --uniform-bucket-level-access \
    --public-access-prevention --default-storage-class=STANDARD
fi
run "$GCLOUD" storage buckets update "$BUCKET" --project="$P" \
  --lifecycle-file=infra/bucket_lifecycle.json --update-labels="$LABELS"

# --- Artifact Registry ------------------------------------------------------
if exists "$GCLOUD" artifacts repositories describe "$AR_REPO" --location="$REGION" --project="$P"; then
  echo "registry: $AR_REPO exists"
else
  run "$GCLOUD" artifacts repositories create "$AR_REPO" --project="$P" \
    --location="$REGION" --repository-format=docker \
    --description="Knight School training/eval images" --labels="$LABELS"
fi
run "$GCLOUD" artifacts repositories set-cleanup-policies "$AR_REPO" --project="$P" \
  --location="$REGION" --policy=infra/registry_cleanup.json --no-dry-run

# --- Service accounts -------------------------------------------------------
sa_email() { echo "$1@$P.iam.gserviceaccount.com"; }

ensure_sa() {
  local name="$1" display="$2"
  if exists "$GCLOUD" iam service-accounts describe "$(sa_email "$name")" --project="$P"; then
    echo "service account: $name exists"
  else
    run "$GCLOUD" iam service-accounts create "$name" --project="$P" --display-name="$display"
  fi
}

project_role() {
  run "$GCLOUD" projects add-iam-policy-binding "$P" \
    --member="serviceAccount:$(sa_email "$1")" --role="$2" --condition=None --quiet \
    --format=none
}

ensure_sa ks-runner "Knight School training/eval runner"
ensure_sa ks-killswitch "Knight School budget kill switch"

# ks-runner: VMs and jobs. instanceAdmin lets a VM delete itself; the
# dedicated project keeps that contained (GCP.md §4).
run "$GCLOUD" storage buckets add-iam-policy-binding "$BUCKET" \
  --member="serviceAccount:$(sa_email ks-runner)" --role=roles/storage.objectAdmin --format=none
for role in roles/artifactregistry.reader roles/logging.logWriter \
            roles/compute.instanceAdmin.v1 roles/aiplatform.user; do
  project_role ks-runner "$role"
done

# ks-killswitch: delete VMs, cancel Vertex jobs, and (opt-in, ADR-013)
# unlink billing. Project Billing Manager on the project is the minimal role
# that can disable the project's billing; no billing-account role needed.
for role in roles/compute.instanceAdmin.v1 roles/aiplatform.user \
            roles/billing.projectManager roles/logging.logWriter; do
  project_role ks-killswitch "$role"
done

echo "== done"
