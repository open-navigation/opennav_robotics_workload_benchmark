# Gemma-4 31B VLM server for the NVIDIA Jetson Thor platform.
#
# Base image is NVIDIA's prebuilt llama.cpp container for Jetson Thor (Jetson AI Lab).
FROM ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-thor

ENV PATH=/usr/local/bin:$PATH

# Single benchmark model/quant (identical on AMD, Orin, and Thor).
ENV LLAMA_MODEL=ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
ENV LLAMA_PORT=8080
# Persist -hf downloads to the mounted HuggingFace cache volume.
ENV LLAMA_CACHE=/root/.cache/huggingface

EXPOSE 8080

# Auto-launch the OpenAI-compatible server on `docker run`.
ENTRYPOINT ["/bin/bash", "-c", "exec llama-server -hf \"$LLAMA_MODEL\" --host 0.0.0.0 --port \"$LLAMA_PORT\" \"$@\"", "--"]
