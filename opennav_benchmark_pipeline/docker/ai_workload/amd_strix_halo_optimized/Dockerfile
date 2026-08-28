# R&D testing image for AMD Strix Halo optimized for vLLM serving of Gemma-4 31B-it-AWQ-4bit
# ---------------------------------------------------------------------------
# Stage 1: rocm-base -- shared ROCm + PyTorch layer
# ---------------------------------------------------------------------------
FROM python:3.12-bookworm AS rocm-base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        git curl ca-certificates cmake ninja-build gcc g++ ccache libdrm-dev \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r render && groupadd -rf video

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh && uv --version

ENV ROCM_PATH=/usr/local/lib/python3.12/site-packages/_rocm_sdk_devel
ENV PATH=/usr/local/lib/python3.12/site-packages/_rocm_sdk_devel/bin:$PATH
ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages/_rocm_sdk_core/share/amd_smi

RUN --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    { \
      echo "torch==2.12.0+rocm10.1.0a20260806"; \
      echo "torchvision==0.27.0+rocm10.1.0a20260806"; \
      echo "torchaudio==2.11.0+rocm10.1.0a20260806"; \
      echo "triton==3.8.0+git4cff872c.rocm10.1.0a20260806"; \
      echo "rocm==10.1.0a20260806"; \
    } > /constraints.txt; \
    cat /constraints.txt; \
    uv pip install --system --break-system-packages --link-mode=copy \
        "torch[device-gfx1151]==2.12.0+rocm10.1.0a20260806" \
        "torchvision[device-gfx1151]==0.27.0+rocm10.1.0a20260806" \
        "torchaudio==2.11.0+rocm10.1.0a20260806" \
        "triton==3.8.0+git4cff872c.rocm10.1.0a20260806" \
        "rocm[devel,libraries,device-gfx1151]==10.1.0a20260806" \
        --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
        --extra-index-url https://pypi.org/simple/ \
        --index-strategy unsafe-first-match \
        --prerelease allow; \
    rocm-sdk init; \
    hipcc --version

# ---------------------------------------------------------------------------
# Stage 2: builder -- compile the vLLM wheel for gfx1151
# ---------------------------------------------------------------------------
FROM rocm-base AS builder

RUN git clone https://github.com/ROCm/vllm.git /src/vllm

WORKDIR /src/vllm

RUN set -eux; \
    git config --global --add safe.directory /src/vllm; \
    git checkout --detach ddd378cfb1e9e9232ae5af18657bc8f99587666c; \
    git log -1 --format='pinned vLLM commit: %H %ad %s'

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --link-mode=copy \
        -c /constraints.txt \
        -r requirements/build/rocm.txt \
        --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
        --extra-index-url https://pypi.org/simple/ \
        --index-strategy unsafe-first-match \
        --prerelease allow

ENV VLLM_TARGET_DEVICE=rocm \
    PYTORCH_ROCM_ARCH=gfx1151 \
    MAX_JOBS=16 \
    CCACHE_DIR=/root/.cache/ccache \
    CMAKE_C_COMPILER_LAUNCHER=ccache \
    CMAKE_CXX_COMPILER_LAUNCHER=ccache \
    CMAKE_HIP_COMPILER_LAUNCHER=ccache

RUN --mount=type=cache,target=/root/.cache/ccache \
    set -eux; \
    ccache --zero-stats || true; \
    python setup.py bdist_wheel --dist-dir=/dist; \
    ccache --show-stats || true; \
    ls -la /dist

# ---------------------------------------------------------------------------
# Stage 3: runtime
# ---------------------------------------------------------------------------
FROM rocm-base AS runtime

COPY --from=builder /dist /dist

RUN --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    set -- /dist/vllm-*.whl; \
    if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then \
        echo "ERROR: expected exactly one vLLM wheel in /dist, found: $*" >&2; \
        exit 1; \
    fi; \
    uv pip install --system --break-system-packages --link-mode=copy \
        -c /constraints.txt \
        "$1[device-gfx1151]" \
        "huggingface_hub" \
        "transformers==5.14.1" \
        --index-url https://rocm.nightlies.amd.com/whl-multi-arch/ \
        --extra-index-url https://pypi.org/simple/ \
        --index-strategy unsafe-first-match \
        --prerelease allow

ENV HF_HOME=/root/.cache/huggingface \
    TRITON_CACHE_DIR=/root/.cache/vllm/triton \
    MIOPEN_USER_DB_PATH=/root/.cache/vllm/miopen \
    MIOPEN_CUSTOM_CACHE_DIR=/root/.cache/vllm/miopen \
    MIOPEN_FIND_DB_PATH=/root/.cache/vllm/miopen \
    PYTHONUNBUFFERED=1

ENV TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1 \
    FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE \
    TORCH_BLAS_PREFER_HIPBLASLT=1 \
    TRITON_HIP_USE_IN_THREAD_TRANSPOSE=0

EXPOSE 8080

ENTRYPOINT ["vllm", "serve", "cyankiwi/gemma-4-31B-it-AWQ-4bit", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--served-model-name", "gemma-4", \
    "--max-model-len", "4096", \
    "--max-num-seqs", "1", \
    "--gpu-memory-utilization", "0.7083", \
    "--limit-mm-per-prompt", "{\"image\": 1, \"video\": 0}", \
    "--mm-processor-cache-gb", "0", \
    "--no-enable-prefix-caching", \
    "--mm-encoder-attn-backend", "TRITON_ATTN", \
    "--speculative-config", "{\"method\":\"mtp\",\"model\":\"google/gemma-4-31B-it-assistant\",\"num_speculative_tokens\":3}"]
