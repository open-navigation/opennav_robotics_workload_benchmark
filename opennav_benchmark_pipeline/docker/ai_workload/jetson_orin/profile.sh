# NVIDIA Jetson Orin AI workload profile.
VLM_EXTRA_RUN_ARGS=(
    --runtime=nvidia
    --volume /ssd/docker/data:/data
    --volume /ssd/docker/.cache/huggingface:/root/.cache/huggingface
)
