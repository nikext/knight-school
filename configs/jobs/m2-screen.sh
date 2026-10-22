#!/bin/bash
# M2 screening job (task M2 §5, §6, §8), run inside the train image on one spot GPU:
#   1. dev500 zero-shot for every candidate profile in SCREEN_MODELS;
#   2. a 5-step GRPO + LoRA + vLLM-colocate smoke for each of SMOKE_MODELS;
#   3. the E0 probe (probe500) for each of PROBE_MODELS.
# Every step runs even if an earlier one fails. After each step /out is pushed to GCS, and a
# preemption retry pulls the earlier attempts' /out and skips the steps already done
# (m2-screen-a100-r2 lost 23 minutes of results to a preemption without this).
set -u
cd "${KS_APP:-/app}"
OUT="${KS_OUT:-/out}"
export KS_PRICE_PER_HOUR="${KS_PRICE_PER_HOUR:-0}"
RUN_PREFIX="${KS_GCS_PREFIX%/attempts/*}"
mkdir -p "$OUT/done"

for ((a = 1; a < KS_ATTEMPT; a++)); do
  python3 -m ks.cloud.gcs pull "$RUN_PREFIX/attempts/$a/out" "$OUT" || true
done
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee "$OUT/gpu.csv"
python3 -c "import torch, vllm, trl, peft, transformers as t; print('torch', torch.__version__, 'vllm', vllm.__version__, 'trl', trl.__version__, 'peft', peft.__version__, 'transformers', t.__version__)" | tee "$OUT/versions.txt"

status=0
step() {  # step NAME LOG CMD...: run once across attempts, push /out afterwards
  local name=$1 log=$2
  shift 2
  if [[ -f "$OUT/done/$name" ]]; then
    echo "[screen] $(date -u +%FT%TZ) $name: done in an earlier attempt, skipping"
    return
  fi
  echo "[screen] $(date -u +%FT%TZ) $name"
  if "$@" > "$log" 2>&1; then
    touch "$OUT/done/$name"
  else
    echo "[screen] $name FAILED"
    status=1
  fi
  tail -25 "$log"
  python3 -m ks.cloud.gcs push "$OUT" "$KS_GCS_PREFIX/out" > /dev/null || echo "[screen] push failed"
}

for m in ${SCREEN_MODELS}; do
  step "eval-$m" "$OUT/eval-$m.log" ks eval "$m" --set dev500 --out "$OUT/eval"
done
for m in ${SMOKE_MODELS}; do
  step "grpo-smoke-$m" "$OUT/grpo-smoke-$m.log" python3 -m ks.train.grpo_smoke --model "$m" \
    --steps 5 --data "${RL_TRAIN}" --out "$OUT/grpo-smoke" --vllm-mem "${SMOKE_VLLM_MEM:-0.45}"
done
for m in ${PROBE_MODELS:-}; do
  step "probe-$m" "$OUT/probe-$m.log" ks eval "$m" --set probe500 --out "$OUT/eval"
done
echo "[screen] $(date -u +%FT%TZ) done, status $status"
exit $status
