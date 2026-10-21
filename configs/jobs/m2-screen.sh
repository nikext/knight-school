#!/bin/bash
# M2 screening job (task M2 §5, §6), run inside the train image on a spot L4.
#   1. dev500 zero-shot for every candidate profile given in SCREEN_MODELS;
#   2. a 5-step GRPO + LoRA + vLLM-colocate smoke for each of SMOKE_MODELS.
# Every step runs even if an earlier one fails; results land in /out (synced to GCS).
set -u
cd /app
export KS_PRICE_PER_HOUR="${KS_PRICE_PER_HOUR:-0}"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee /out/gpu.csv
python3 -c "import torch, vllm, trl, peft, transformers as t; print('torch', torch.__version__, 'vllm', vllm.__version__, 'trl', trl.__version__, 'peft', peft.__version__, 'transformers', t.__version__)" | tee /out/versions.txt
status=0
for m in ${SCREEN_MODELS}; do
  echo "[screen] $(date -u +%FT%TZ) eval $m"
  ks eval "$m" --set dev500 --out /out/eval > "/out/eval-$m.log" 2>&1 || { echo "[screen] eval $m FAILED"; status=1; }
  tail -25 "/out/eval-$m.log"
done
for m in ${SMOKE_MODELS}; do
  echo "[screen] $(date -u +%FT%TZ) grpo smoke $m"
  python3 -m ks.train.grpo_smoke --model "$m" --steps 5 --data "${RL_TRAIN}" --out /out/grpo-smoke \
    > "/out/grpo-smoke-$m.log" 2>&1 || { echo "[screen] grpo smoke $m FAILED"; status=1; }
  tail -5 "/out/grpo-smoke-$m.log"
done
echo "[screen] $(date -u +%FT%TZ) done, status $status"
exit $status
