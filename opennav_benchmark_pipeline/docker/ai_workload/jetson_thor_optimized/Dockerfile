# Optimized Gemma-4 31B VLM server for NVIDIA Jetson Thor using FP4, vLLM, speculative decoding.
#
# Base image
FROM vllm/vllm-openai:latest

# Ensure HuggingFace downloads land in the mounted cache volume.
ENV HF_HOME=/root/.cache/huggingface

EXPOSE 8080

# Auto-launch the OpenAI-compatible vLLM server on `docker run`.
ENTRYPOINT ["vllm", "serve", "nvidia/Gemma-4-31B-IT-NVFP4", \
    "--port", "8080", \
    "--served-model-name", "gemma-4", \
    "--max-model-len", "8192", \
    "--gpu-memory-utilization", "0.7", \
    "--enable-auto-tool-choice", \
    "--reasoning-parser", "gemma4", \
    "--tool-call-parser", "gemma4", \
    "--attention-backend", "TRITON_ATTN", \
    "--default-chat-template-kwargs", "{\"enable_thinking\":true}", \
    "--speculative-config", "{\"method\":\"mtp\",\"model\":\"google/gemma-4-31B-it-assistant\",\"num_speculative_tokens\":3}"]
