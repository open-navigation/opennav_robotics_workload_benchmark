#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Standalone launcher for the per-platform VLM inference server.
#
# Resolves the platform profile from the image tag suffix the same way
# run_benchmark.sh does (docker/ai_workload/<suffix>/profile.sh) and applies its
# extra `docker run` flags. Use this to serve the VLM on its own (e.g. to
# pre-download the model, smoke-test the endpoint, or run it on a separate HIL
# host); run_benchmark.sh launches the same image as part of a full benchmark.
#
# Usage:
#   ./run_vlm.sh <image> [extra llama-server args...]
#   e.g. ./run_vlm.sh opennav_benchmark/ai_workload:amd_strix_halo
#
# The image may also be supplied via the VLM_IMAGE env var instead of an arg.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ge 1 ]]; then
    VLM_IMAGE="$1"
    shift
else
    VLM_IMAGE="${VLM_IMAGE:-}"
fi

VLM_NAME="${VLM_NAME:-opennav_vlm}"
SHM_SIZE="${SHM_SIZE:-8g}"
XAUTH_PATH="${XAUTHORITY:-${HOME}/.Xauthority}"

if [[ -z "${VLM_IMAGE}" ]]; then
    echo "ERROR: no VLM image given." >&2
    echo "Usage: $0 <image> [extra llama-server args...]" >&2
    echo "       e.g. $0 opennav_benchmark/ai_workload:amd_strix_halo" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not on PATH" >&2
    exit 1
fi

# Resolve the AI workload run-flag profile from the VLM image tag suffix (text after the last ':').
VLM_EXTRA_RUN_ARGS=()
VLM_PROFILE_KEY="${VLM_IMAGE##*:}"
VLM_PROFILE="${SCRIPT_DIR}/docker/ai_workload/${VLM_PROFILE_KEY}/profile.sh"
if [[ ! -f "${VLM_PROFILE}" ]]; then
    echo "ERROR: VLM_IMAGE='${VLM_IMAGE}' has no matching AI workload profile at ${VLM_PROFILE}" >&2
    exit 1
fi
# shellcheck source=/dev/null
source "${VLM_PROFILE}"   # sets VLM_EXTRA_RUN_ARGS

echo "Launching VLM container ${VLM_NAME}"
echo "  VLM_IMAGE=${VLM_IMAGE}"
echo "  VLM_PROFILE=${VLM_PROFILE}"
echo "  VLM_EXTRA_RUN_ARGS=${VLM_EXTRA_RUN_ARGS[*]:-<none>}"

exec docker run --rm -it --init \
    --name "${VLM_NAME}" \
    --net=host --ipc=host --privileged \
    --shm-size="${SHM_SIZE}" \
    --env "DISPLAY=${DISPLAY:-}" \
    --env "QT_X11_NO_MITSHM=1" \
    --volume "${XAUTH_PATH}:/root/.Xauthority:ro" \
    --volume "/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    ${VLM_EXTRA_RUN_ARGS[@]+"${VLM_EXTRA_RUN_ARGS[@]}"} \
    "${VLM_IMAGE}" \
    "$@"
