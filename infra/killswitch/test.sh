#!/usr/bin/env bash
# End-to-end kill-switch test (M0 task §6). Needs a running labelled VM, started with
#   ks launch configs/runs/m0-killswitch-test.yaml --confirm
# Then: an under-threshold message must leave it alone, an over-threshold one
# must delete it. The messages are synthetic and never ks-net >= $5, so this
# test can never detach billing.
set -euo pipefail

cd "$(dirname "$0")/../.."
# shellcheck disable=SC1091
set -a; source .env; set +a
GCLOUD="${GCLOUD:-$HOME/google-cloud-sdk/bin/gcloud}"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
P="$GOOGLE_CLOUD_PROJECT"
VM=ks-m0-killswitch-test-a1
ZONE=us-central1-a

# Prints the VM status, or nothing once it is gone (never fails, so set -e doesn't fire).
exists() { "$GCLOUD" compute instances describe "$VM" --zone="$ZONE" --project="$P" --format='value(status)' 2>/dev/null || true; }
publish() {
  "$GCLOUD" pubsub topics publish ks-budget --project="$P" --message="$1" --format=none
}
msg() {  # name cost amount
  printf '{"budgetDisplayName":"%s","costAmount":%s,"budgetAmount":%s,"costIntervalStart":"2026-10-01T00:00:00Z","currencyCode":"USD","budgetAmountType":"SPECIFIED_AMOUNT"}' "$1" "$2" "$3"
}

[[ -n "$(exists)" ]] || { echo "$VM is not running; launch it first" >&2; exit 1; }
echo "== $VM is $(exists)"

echo "== 1. under threshold: ks-total-gross 100/540 (19%) -> must do nothing"
publish "$(msg ks-total-gross 100 540)"
sleep 90
status="$(exists)"
[[ -n "$status" ]] || { echo "FAIL: VM deleted on an under-threshold message" >&2; exit 1; }
echo "ok: $VM still $status"

echo "== 2. over threshold: ks-total-gross 500/540 (93%) -> must delete $VM"
publish "$(msg ks-total-gross 500 540)"
for _ in $(seq 1 30); do
  status="$(exists)"
  [[ -z "$status" ]] && break
  echo "  ... $status"
  sleep 10
done
[[ -z "$(exists)" ]] || { echo "FAIL: $VM still exists after 5 minutes" >&2; exit 1; }
echo "ok: $VM deleted"

echo "== function log (decisions):"
"$GCLOUD" functions logs read ks-killswitch --project="$P" --region="${REGION:-us-central1}" --limit=50 \
  | grep -E 'ks-killswitch:|delete ' || true
echo "PASS"
