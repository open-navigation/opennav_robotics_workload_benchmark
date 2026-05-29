# Gemma-4 31B VLM server for the NVIDIA Jetson Orin AGX platform.
#
# Base image is NVIDIA's prebuilt llama.cpp container for Jetson (Jetson AI Lab).
FROM ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin

ENV PATH=/usr/local/bin:$PATH

# Single benchmark model/quant (identical on AMD, Orin, and Thor).
ENV LLAMA_MODEL=ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
ENV LLAMA_PORT=8080
# Persist -hf downloads to the mounted HuggingFace cache volume.
ENV LLAMA_CACHE=/root/.cache/huggingface

# Orin requires the vision encoder to be run on CPU to not blow out the GPU memory
# CUDA error: out of memory
#   current device: 0, in function alloc at /opt/llama.cpp/ggml/src/ggml-cuda/ggml-cuda.cu:526
#   cuMemAddressReserve(&pool_addr, CUDA_POOL_VMM_MAX_SIZE, 0, 0, 0)
# ...
# #11 0x0000ffffb3527f7c in clip_image_batch_encode(clip_ctx*, int, clip_image_f32_batch const*, float*) () from /usr/local/lib/libmtmd.so.0
# #12 0x0000ffffb34b4994 in mtmd_encode () from /usr/local/lib/libmtmd.so.0
# #13 0x0000ffffb3522644 in mtmd_helper_eval_chunk_single () from /usr/local/lib/libmtmd.so.0
ENV LLAMA_ARG_MMPROJ_OFFLOAD=0
# -ngl 32 can also fix the issue, but that is tuned to this particular application and will not generalize to everyone's workloads.
# It essentially reduces the resources given to another part of the model pipeline to free up the resources for the vision encoder
# to get what it wants, considering the total system load. Rather than a heuristically driven 'does it work now' solution, we select
# to fix the root cause, even if it comes at the cost of some performance. Tuning -ngl 32 to your application will improve CPU performance some.

EXPOSE 8080

# Auto-launch the OpenAI-compatible server on `docker run`.
ENTRYPOINT ["/bin/bash", "-c", "exec llama-server -hf \"$LLAMA_MODEL\" --host 0.0.0.0 --port \"$LLAMA_PORT\" --log-file /var/log/llama/server.log \"$@\"", "--"]
