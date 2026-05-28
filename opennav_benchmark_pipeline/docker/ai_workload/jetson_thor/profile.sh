# NVIDIA Jetson Thor AI workload profile.
VLM_EXTRA_RUN_ARGS=(
    --runtime=nvidia
    --volume "${HOME}/.cache/huggingface:/root/.cache/huggingface"
)
