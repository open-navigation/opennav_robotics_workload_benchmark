# Optimized Gemma-4 31B VLM server for NVIDIA Jetson Thor using FP4, vLLM, speculative decoding.
#
# Base image is NVIDIA's prebuilt vLLM container (Jetson AI Lab).
FROM ghcr.io/nvidia-ai-iot/vllm:gemma4-jetson-thor

# Persist -hf downloads to the mounted HuggingFace cache volume.
ENV LLAMA_CACHE=/root/.cache/huggingface

EXPOSE 8080

# Auto-launch the OpenAI-compatible vLLM server on `docker run`.
ENTRYPOINT ["vllm", "serve", "nvidia/Gemma-4-31B-IT-NVFP4", \
    "--port", "8080", \
    "--gpu-memory-utilization", "0.8", \
    "--enable-auto-tool-choice", \
    "--reasoning-parser", "gemma4", \
    "--tool-call-parser", "gemma4", \
    "--speculative-config", "{\"method\":\"mtp\",\"model\":\"google/gemma-4-31B-it-assistant\",\"num_speculative_tokens\":3}"]
