#!/bin/bash
# Startup script for every ks VM (GCP.md §5). `ks launch` passes the job in
# instance metadata. This script:
#   1. writes runs/<id>/attempts/<n>/started to GCS,
#   2. pulls the image and runs the command under `timeout`,
#   3. syncs /out and the log to GCS and writes `ended` with the exit code,
#   4. deletes its own VM -- from an EXIT trap, so errors delete it too.
# --max-run-duration (set by ks launch) is the backstop if this script dies.
set -uo pipefail

MD=http://metadata.google.internal/computeMetadata/v1/instance
md() { curl -sf -H 'Metadata-Flavor: Google' "$MD/$1"; }
attr() { md "attributes/$1"; }
stamp() { date -u +%FT%TZ; }

NAME=$(md name)
ZONE=$(md zone | awk -F/ '{print $NF}')
RUN_ID=$(attr ks-run-id)
ATTEMPT=$(attr ks-attempt)
BUCKET=$(attr ks-bucket)
IMAGE=$(attr ks-image)
CMD=$(attr ks-command | base64 -d)
JOB_SECONDS=$(attr ks-job-seconds)
GPUS=$(attr ks-gpus || echo 0)
PREFIX="$BUCKET/runs/$RUN_ID/attempts/$ATTEMPT"

WORK=/var/ks
OUT=$WORK/out
LOG=$WORK/job.log
ENV_FILE=$WORK/job.env
mkdir -p "$OUT"
attr ks-env | base64 -d > "$ENV_FILE" || : > "$ENV_FILE"
printf 'KS_RUN_ID=%s\nKS_ATTEMPT=%s\nKS_OUT=/out\nKS_GCS_PREFIX=%s\n' "$RUN_ID" "$ATTEMPT" "$PREFIX" >> "$ENV_FILE"

put() { printf '%s\n' "$2" | gcloud storage cp - "$PREFIX/$1" --quiet; }
self_delete() { gcloud compute instances delete "$NAME" --zone "$ZONE" --quiet; }

# The Deep Learning VM image (common-cu129-ubuntu-2404-nvidia-580) ships the
# NVIDIA driver but not Docker (found in the M0 smoke), so install what is
# missing. The apt lock timeout waits out apt-daily on first boot.
APT=(apt-get -o DPkg::Lock::Timeout=300 -y -qq)
ensure_docker() {
  command -v docker >/dev/null && return 0
  echo "[ks] $(stamp) installing docker.io"
  DEBIAN_FRONTEND=noninteractive "${APT[@]}" update && DEBIAN_FRONTEND=noninteractive "${APT[@]}" install docker.io
  systemctl enable --now docker
}
ensure_nvidia_runtime() {
  docker info 2>/dev/null | grep -qi 'runtimes.*nvidia' && return 0
  if ! command -v nvidia-ctk >/dev/null; then
    echo "[ks] $(stamp) installing nvidia-container-toolkit"
    local key=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --batch --yes --dearmor -o "$key"
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed "s#deb https://#deb [signed-by=$key] https://#g" > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    DEBIAN_FRONTEND=noninteractive "${APT[@]}" update && DEBIAN_FRONTEND=noninteractive "${APT[@]}" install nvidia-container-toolkit
  fi
  nvidia-ctk runtime configure --runtime=docker && systemctl restart docker
}

# Spot VMs are deleted, never restarted; but if this ever runs twice, don't redo the job.
if gcloud storage ls "$PREFIX/ended" >/dev/null 2>&1; then
  self_delete
  exit 0
fi

RC=1
finish() {
  gcloud storage rsync -r "$OUT" "$PREFIX/out" --quiet || true
  gcloud storage cp "$LOG" "$PREFIX/job.log" --quiet || true
  put ended "{\"ts\":\"$(stamp)\",\"exit_code\":$RC}" || true
  self_delete
}
trap finish EXIT

put started "{\"ts\":\"$(stamp)\",\"instance\":\"$NAME\",\"zone\":\"$ZONE\"}"
T0=$(date +%s)
left() { echo $(( JOB_SECONDS - ($(date +%s) - T0) )); }

{
  echo "[ks] $(stamp) run=$RUN_ID attempt=$ATTEMPT image=$IMAGE budget=${JOB_SECONDS}s"
  if [[ "$IMAGE" == "host" ]]; then
    timeout --signal=TERM --kill-after=60 "$(left)" bash -c "$CMD"
  else
    if (( GPUS > 0 )); then nvidia-smi || exit 1; fi
    ensure_docker || exit 1
    if (( GPUS > 0 )); then ensure_nvidia_runtime || exit 1; fi
    echo "[ks] $(stamp) $(docker --version); $(nvidia-ctk --version 2>/dev/null | head -1)"
    gcloud auth configure-docker us-central1-docker.pkg.dev,europe-west4-docker.pkg.dev --quiet
    timeout "$(left)" docker pull "$IMAGE" || exit 1
    GPU_FLAGS=()
    (( GPUS > 0 )) && GPU_FLAGS=(--gpus all)
    timeout --signal=TERM --kill-after=60 "$(left)" \
      docker run --rm "${GPU_FLAGS[@]}" --env-file "$ENV_FILE" -v "$OUT:/out" "$IMAGE" bash -c "$CMD"
  fi
} > >(tee "$LOG") 2>&1
RC=$?
wait $! 2>/dev/null || true  # let tee flush the log before finish() uploads it
echo "[ks] $(stamp) exit code $RC" | tee -a "$LOG"
exit "$RC"
