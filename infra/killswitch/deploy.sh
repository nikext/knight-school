#!/usr/bin/env bash
# Deploy the ks-killswitch Cloud Run function (GCP.md §7). DRY_RUN=1 prints.
# Re-running redeploys, which is how config changes are applied.
set -euo pipefail

cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
set -a; source .env; set +a
GCLOUD="${GCLOUD:-$HOME/google-cloud-sdk/bin/gcloud}"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
P="$GOOGLE_CLOUD_PROJECT"
SA="${KILLSWITCH_SA:?set in .env}"
REGION="${REGION:-us-central1}"
DRY_RUN="${DRY_RUN:-0}"
# The user opted in to billing detach at net >= $5 in M0 (dedicated project, ADR-013).
DETACH="${KS_DETACH_BILLING:-1}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; fi
}

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
cat > "$ENV_FILE" <<EOF
KS_PROJECT: "$P"
KS_REGIONS: "us-central1,europe-west4"
KS_DETACH_BILLING: "$DETACH"
EOF

if ! "$GCLOUD" pubsub topics describe ks-budget --project="$P" >/dev/null 2>&1; then
  run "$GCLOUD" pubsub topics create ks-budget --project="$P" --labels=app=knight-school
fi

run "$GCLOUD" functions deploy ks-killswitch --project="$P" --gen2 \
  --region="$REGION" --runtime=python312 --source=infra/killswitch --entry-point=handle \
  --trigger-topic=ks-budget --service-account="$SA" --trigger-service-account="$SA" \
  --env-vars-file="$ENV_FILE" --ingress-settings=internal-only \
  --max-instances=1 --memory=256Mi --timeout=300s --update-labels=app=knight-school

# The Eventarc trigger calls the function as $SA.
run "$GCLOUD" functions add-invoker-policy-binding ks-killswitch --project="$P" \
  --region="$REGION" --member="serviceAccount:$SA"
