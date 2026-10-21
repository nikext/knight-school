#!/usr/bin/env bash
# The three ks budgets (BUDGET.md §3.5, GCP.md §7). Idempotent; DRY_RUN=1 prints.
# All publish to Pub/Sub topic ks-budget, which the ks-killswitch function reads.
#
# The period is a fixed custom range, not a calendar month: a monthly budget
# would reset on Nov 1 and let the project spend its gross cap twice.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a
GCLOUD="${GCLOUD:-$HOME/google-cloud-sdk/bin/gcloud}"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
P="$GOOGLE_CLOUD_PROJECT"
DRY_RUN="${DRY_RUN:-0}"
START=2026-10-01
END=2027-04-30
VERTEX_SERVICE=services/C7E2-9256-1C43   # Vertex AI, verified via the Catalog API /v1/services
TOPIC="projects/$P/topics/ks-budget"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else printf '+'; printf ' %q' "$@"; printf '\n'; "$@"; fi
}

# Looked up at run time so the billing account id never lands in the repo.
BA="$("$GCLOUD" billing projects describe "$P" --format='value(billingAccountName)')"
BA="${BA#billingAccounts/}"
[[ -n "$BA" ]] || { echo "project $P has no billing account" >&2; exit 1; }

if ! "$GCLOUD" pubsub topics describe ks-budget --project="$P" >/dev/null 2>&1; then
  run "$GCLOUD" pubsub topics create ks-budget --project="$P" --labels=app=knight-school
fi

existing="$("$GCLOUD" billing budgets list --billing-account="$BA" --format='value(displayName)')"

budget() {  # name amount credit-treatment thresholds... [-- extra flags]
  local name=$1 amount=$2 credits=$3; shift 3
  local rules=() extra=()
  while (($#)); do
    if [[ "$1" == "--" ]]; then shift; extra=("$@"); break; fi
    rules+=("--threshold-rule=percent=$1"); shift
  done
  if grep -qx "$name" <<<"$existing"; then
    echo "budget $name exists"
    return
  fi
  run "$GCLOUD" billing budgets create --billing-account="$BA" \
    --display-name="$name" --budget-amount="${amount}USD" \
    --filter-projects="projects/$P" --credit-types-treatment="$credits" \
    --start-date="$START" --end-date="$END" \
    "${rules[@]}" --notifications-rule-pubsub-topic="$TOPIC" "${extra[@]}"
}

# Gross = before credits: what the project would cost if credits vanished.
budget ks-total-gross 540 exclude-all-credits 0.5 0.75 0.9 1.0
budget ks-vertex-gross 180 exclude-all-credits 0.5 0.75 0.9 1.0 -- --filter-services="$VERTEX_SERVICE"
# Net = after credits: anything above $0 is real money.
budget ks-net 5 include-all-credits 0.2 1.0

echo "== budgets on the billing account for $P:"
[[ "$DRY_RUN" == "1" ]] || "$GCLOUD" billing budgets list --billing-account="$BA" \
  --format='table(displayName,amount.specifiedAmount.units,budgetFilter.creditTypesTreatment)' \
  | grep -E 'DISPLAY|ks-'
