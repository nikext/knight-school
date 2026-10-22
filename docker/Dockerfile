# One image for evals, SFT and GRPO (TRAINING.md §8, ADR-016).
# Base: vLLM 0.31.0 (torch 2.13.0, CUDA 12.9), the newest vLLM that TRL 1.16.0 supports.
# The digest pins the exact image; the tag is for humans.
FROM vllm/vllm-openai:v0.31.0-x86_64-cu129@sha256:b18abb2df97b8f798e81862bd93f872ea18613372e2c3adc0cc2ac21e66ac12f

ENTRYPOINT []
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HUB_ENABLE_HF_TRANSFER=0

# Training libraries and our runtime deps (pyproject `train` extra). The base image's torch,
# vLLM, triton, FlashInfer, numpy, numba and opentelemetry versions are constraints: the first
# build let pip upgrade numpy to 2.5 under numba's <2.5 pin. Freezing the whole base was too
# strict (its fsspec is newer than any `datasets` allows). The build fails if `pip check`
# reports a conflict the base image didn't have. Fewer is fine: the base's own conflict
# (nvidia-nccl-cu12 2.30.7 vs torch's ==2.29.7 pin) goes away when pip installs torch's pin.
COPY docker/requirements.txt /tmp/requirements.txt
RUN (python3 -m pip check > /tmp/check-base.txt 2>&1 || true) \
 && python3 -m pip freeze | grep -iE '^(torch|torchvision|torchaudio|vllm|triton|flashinfer-[a-z-]+|numpy|numba|llvmlite|xformers|opentelemetry-[a-z-]+)==' > /tmp/constraints.txt \
 && python3 -m pip install --no-cache-dir -c /tmp/constraints.txt -r /tmp/requirements.txt \
 && (python3 -m pip check > /tmp/check-after.txt 2>&1 || true) \
 && sort /tmp/check-base.txt > /tmp/a && sort /tmp/check-after.txt > /tmp/b \
 && { comm -13 /tmp/a /tmp/b | tee /tmp/new-conflicts.txt; ! grep -q . /tmp/new-conflicts.txt; } \
 && python3 -c "import torch, vllm, trl, peft, transformers, numpy; print('torch', torch.__version__, 'vllm', vllm.__version__, 'trl', trl.__version__, 'peft', peft.__version__, 'transformers', transformers.__version__, 'numpy', numpy.__version__)"

# The base ships a torchcodec built for CUDA 13 (it loads libnvrtc.so.13, absent from this
# cu129 image), and `datasets` imports it, which breaks `trl.GRPOTrainer` on import (found in
# the first screening run). We never decode audio or video, so it goes.
RUN python3 -m pip uninstall -y torchcodec \
 && python3 -c "from trl import GRPOConfig, GRPOTrainer; from vllm import LLM, SamplingParams; import datasets, peft; print('imports ok')"

COPY pyproject.toml README.md LICENSE ./
COPY ks ./ks
COPY configs ./configs
COPY costs ./costs
COPY evals ./evals
# Editable, so ks.cloud.config.REPO resolves to /app (configs/, evals/, costs/) and not to
# site-packages; the first screening run failed on exactly that. The smoke below runs the
# CPU paths the GPU jobs depend on, so a packaging bug fails the build instead of a GPU run.
RUN python3 -m pip install --no-cache-dir --no-deps -e . && mkdir -p /out \
 && ks eval random --set dev500 --limit 5 --out /tmp/smoke \
 && ks eval random --set probe500 --limit 8 --out /tmp/smoke \
 && python3 -c "from ks.eval import profile; [profile.load(m) for m in ('qwen3-1.7b', 'qwen3.5-2b', 'gemma4-e2b')]" \
 && python3 -m ks.train.grpo_smoke --help > /dev/null && python3 -m ks.train.grpo --help > /dev/null \
 && python3 -c "from ks.train import config; config.load('configs/train/grpo_dense.yaml'); config.load('configs/train/grpo_sparse.yaml')" \
 && bash -n configs/jobs/m3-grpo.sh && python3 -c 'import tensorboardX' && rm -rf /tmp/smoke

ARG GIT_SHA=unknown
ENV KS_GIT_SHA=${GIT_SHA}
