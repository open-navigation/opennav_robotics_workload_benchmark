#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Simulation parameters
# =============================================================================

SIM_IMAGE="${SIM_IMAGE:-opennav_benchmark/robotic_amr_simulation:jazzy}"
SIM_NAME="${SIM_NAME:-opennav_sim}"

# =============================================================================

XAUTH_PATH="${XAUTHORITY:-${HOME}/.Xauthority}"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not on PATH" >&2
    exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
    echo "WARNING: DISPLAY is unset; Gazebo GUI and RViz will not appear on host" >&2
fi

exec docker run --rm -it --init \
    --name "${SIM_NAME}" \
    --net=host --ipc=host --privileged \
    --shm-size=2g \
    --env "DISPLAY=${DISPLAY:-}" \
    --env "QT_X11_NO_MITSHM=1" \
    --volume "${XAUTH_PATH}:/root/.Xauthority:ro" \
    --volume "/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    "${SIM_IMAGE}" \
    "$@"
