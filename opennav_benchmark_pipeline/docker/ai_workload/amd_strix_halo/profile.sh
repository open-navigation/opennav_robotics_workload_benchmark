# AMD Strix Halo (Ryzen AI Max+) AI workload profile.
VLM_EXTRA_RUN_ARGS=(
    --cap-add=SYS_PTRACE
    --device=/dev/kfd
    --device=/dev/dri
    --security-opt seccomp=unconfined
    --group-add video
    --group-add render
    --volume "$HOME/llamacpp_cache/huggingface:/root/.cache/huggingface"
)
