# Optimized Gemma-4 31B VLM server for AMD Strix Halo using vLLM, speculative decoding.
#
# Base image, using latest bleeding-edge version of the ROCm vLLM image
# Exact library versions for reproduction can be found in the ROCm vLLM repository docs: https://github.com/ROCm/vllm/tree/gfx11#getting-started
# Use vllm/vllm-openai-rocm:latest for released version after Feb'27 (bleeding-edge updates merged)
FROM ghcr.io/rocm/vllm/gfx11:latest

# Ensure HuggingFace downloads land in the mounted cache volume.
ENV HF_HOME=/root/.cache/huggingface

EXPOSE 8080

ENTRYPOINT ["vllm", "serve", "cyankiwi/gemma-4-31B-it-AWQ-4bit", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--served-model-name", "gemma-4", \
    "--max-model-len", "8192", \
    "--max-num-seqs", "1", \
    "--gpu-memory-utilization", "0.7083", \
    "--limit-mm-per-prompt", "{\"image\": 1, \"video\": 0}", \
    "--mm-processor-cache-gb", "0", \
    "--no-enable-prefix-caching", \
    "--default-chat-template-kwargs", "{\"enable_thinking\":true}", \
    "--enable-auto-tool-choice", \
    "--reasoning-parser", "gemma4", \
    "--tool-call-parser", "gemma4", \
    "--mm-encoder-attn-backend", "TRITON_ATTN", \
    "--speculative-config", "{\"method\":\"mtp\",\"model\":\"google/gemma-4-31B-it-assistant\",\"num_speculative_tokens\":3}"]
