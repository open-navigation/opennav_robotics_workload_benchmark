# Gemma-4 31B VLM server for the AMD Strix Halo platform.
#
# Base image is produced by `ryzers build --name llamacpp llamacpp`
# (https://github.com/amdresearch/ryzers); see amd.md section 4.
FROM llamacpp

ENV PATH=/ryzers/llamacpp/build/bin:$PATH

# Single benchmark model/quant (identical on AMD, Orin, and Thor).
ENV LLAMA_MODEL=ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
ENV LLAMA_PORT=8080
# Persist -hf downloads to the mounted HuggingFace cache volume.
ENV LLAMA_CACHE=/root/.cache/huggingface

EXPOSE 8080

# Auto-launch the OpenAI-compatible server on `docker run`.
ENTRYPOINT ["/bin/bash", "-c", "exec llama-server -hf \"$LLAMA_MODEL\" --host 0.0.0.0 --port \"$LLAMA_PORT\" \"$@\"", "--"]
