#!/bin/bash
# GRPO job (task M3 §4, §5, §8), run inside the train image on one spot GPU:
#   1. train: python -m ks.train.grpo (resumes from the run's newest complete checkpoint);
#   2. eval the final merged model on $TEST_SET (default test2000);
#   3. optionally E0 (probe500) on it (PROBE=1).
# Env: TRAIN_CONFIG, TRAIN_SETS ("key=value ..." passed as --set), MODEL (profile), TEST_SET,
# TEST_LIMIT, PROBE, PASSK (dev500 pass@8), START_CKPT (E5b: also evaluate this start model and
# the base model on $TEST_SET under $MODEL's prompt); TEST_SET=none skips the eval (throughput runs). A retry pulls the earlier
# attempts' /out and skips finished steps, as m2-screen.sh does. SIGTERM (preemption) is
# forwarded to the trainer, which exits 143 after leaving a marker; this script then exits 143.
set -u
cd "${KS_APP:-/app}"
OUT="${KS_OUT:-/out}"
export KS_PRICE_PER_HOUR="${KS_PRICE_PER_HOUR:-0}"
RUN_PREFIX="${KS_GCS_PREFIX%/attempts/*}"
MODEL="${MODEL:-qwen3.5-2b}"
TEST_SET="${TEST_SET:-test2000}"
mkdir -p "$OUT/done"

for ((a = 1; a < KS_ATTEMPT; a++)); do
  python3 -m ks.cloud.gcs pull "$RUN_PREFIX/attempts/$a/out" "$OUT" > /dev/null || true
done
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee "$OUT/gpu-attempt-$KS_ATTEMPT.csv"

child=
trap '[[ -n "$child" ]] && kill -TERM "$child" 2>/dev/null' TERM

step() {  # step NAME LOG CMD...: run once across attempts; exit 143 if it was preempted
  local name=$1 log=$2 rc
  shift 2
  if [[ -f "$OUT/done/$name" ]]; then
    echo "[job] $(date -u +%FT%TZ) $name: done in an earlier attempt, skipping"
    return 0
  fi
  echo "[job] $(date -u +%FT%TZ) $name"
  "$@" > >(tee -a "$log") 2>&1 &
  child=$!
  wait "$child"; rc=$?
  while kill -0 "$child" 2>/dev/null; do wait "$child"; rc=$?; done  # wait returns early on a trap
  child=
  python3 -m ks.cloud.gcs push "$OUT" "$KS_GCS_PREFIX/out" > /dev/null || echo "[job] push failed"
  if [[ $rc -eq 0 ]]; then
    touch "$OUT/done/$name"
  elif [[ $rc -eq 143 ]]; then
    echo "[job] $name stopped by SIGTERM; the next attempt resumes"
    exit 143
  else
    echo "[job] $name FAILED (exit $rc)"
    exit "$rc"
  fi
}

read -ra sets <<< "${TRAIN_SETS:-}"
set_args=()
for s in "${sets[@]}"; do set_args+=(--set "$s"); done
step train "$OUT/train.log" python3 -m ks.train.grpo --config "$TRAIN_CONFIG" "${set_args[@]}"

ckpt=/tmp/ks-work/final/merged
[[ -d "$ckpt" ]] || ckpt="$RUN_PREFIX/final/merged"
limit=()
[[ -n "${TEST_LIMIT:-}" ]] && limit=(--limit "$TEST_LIMIT")
if [[ "$TEST_SET" != none ]]; then
  step "eval-$TEST_SET" "$OUT/eval-$TEST_SET.log" \
    ks eval "$MODEL" --set "$TEST_SET" --ckpt "$ckpt" --run "$KS_RUN_ID" --out "$OUT/eval" "${limit[@]}"
fi
if [[ "${PROBE:-0}" == 1 ]]; then
  step probe "$OUT/probe.log" ks eval "$MODEL" --set probe500 --ckpt "$ckpt" --run "$KS_RUN_ID" --out "$OUT/eval"
fi
if [[ "${PASSK:-0}" == 1 ]]; then  # pass@k on dev500: 8 samples at T = 1 (task M4 §7)
  step pass8 "$OUT/pass8.log" ks eval "$MODEL" --set dev500 --n 8 --ckpt "$ckpt" --run "$KS_RUN_ID-pass8" --out "$OUT/eval"
fi
if [[ -n "${START_CKPT:-}" && "$TEST_SET" != none ]]; then  # E5b: the start and the base under this prompt
  step eval-start "$OUT/eval-start.log" \
    ks eval "$MODEL" --set "$TEST_SET" --ckpt "$START_CKPT" --run "$KS_RUN_ID-start" --out "$OUT/eval"
  step eval-base "$OUT/eval-base.log" ks eval "$MODEL" --set "$TEST_SET" --run "$MODEL" --out "$OUT/eval"
fi
echo "[job] $(date -u +%FT%TZ) done"
