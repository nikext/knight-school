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
# reports anything the base image didn't.
COPY docker/requirements.txt /tmp/requirements.txt
RUN (python3 -m pip check > /tmp/check-base.txt 2>&1 || true) \
 && python3 -m pip freeze | grep -iE '^(torch|torchvision|torchaudio|vllm|triton|flashinfer-[a-z-]+|numpy|numba|llvmlite|xformers|opentelemetry-[a-z-]+)==' > /tmp/constraints.txt \
 && python3 -m pip install --no-cache-dir -c /tmp/constraints.txt -r /tmp/requirements.txt \
 && (python3 -m pip check > /tmp/check-after.txt 2>&1 || true) \
 && diff /tmp/check-base.txt /tmp/check-after.txt \
 && python3 -c "import torch, vllm, trl, peft, transformers, numpy; print('torch', torch.__version__, 'vllm', vllm.__version__, 'trl', trl.__version__, 'peft', peft.__version__, 'transformers', transformers.__version__, 'numpy', numpy.__version__)"

COPY pyproject.toml README.md LICENSE ./
COPY ks ./ks
COPY configs ./configs
COPY costs ./costs
COPY evals ./evals
RUN python3 -m pip install --no-cache-dir --no-deps . && mkdir -p /out

ARG GIT_SHA=unknown
ENV KS_GIT_SHA=${GIT_SHA}
