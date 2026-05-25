#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Benchmark parameters
# =============================================================================

AUTONOMY_IMAGE="${AUTONOMY_IMAGE:-opennav_benchmark/robotic_amr_workload:jazzy}"
VLM_IMAGE="${VLM_IMAGE:-}"
METRICS_SCRIPT="${METRICS_SCRIPT:-}"

BENCHMARK_DURATION_SEC="${BENCHMARK_DURATION_SEC:-180}"
STARTUP_WAIT_SEC="${STARTUP_WAIT_SEC:-10}"
STATUS_LOG_INTERVAL_SEC="${STATUS_LOG_INTERVAL_SEC:-30}"
SHUTDOWN_GRACE_SEC="${SHUTDOWN_GRACE_SEC:-15}"

LOG_PARENT_DIR="${LOG_PARENT_DIR:-./opennav_benchmark_logs}"

# =============================================================================
# Internal methods and general data
# =============================================================================

RUN_TIMESTAMP="$(date +%s)"
AUTONOMY_NAME="opennav_autonomy_${RUN_TIMESTAMP}"
VLM_NAME="opennav_vlm_${RUN_TIMESTAMP}"

AUTONOMY_LAUNCHED=0
VLM_LAUNCHED=0
METRICS_PID=""
CLEANED_UP=0

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fmt_duration() {
    local s=$1
    printf '%02d:%02d' $((s / 60)) $((s % 60))
}

cleanup() {
    if [[ "${CLEANED_UP}" -eq 1 ]]; then
        return
    fi
    CLEANED_UP=1

    log "Cleanup starting..."

    if [[ -n "${METRICS_PID}" ]] && kill -0 "${METRICS_PID}" 2>/dev/null; then
        log "Stopping metrics capture (pid ${METRICS_PID})"
        kill -TERM "${METRICS_PID}" 2>/dev/null || true
        for _ in 1 2 3 4 5; do
            if ! kill -0 "${METRICS_PID}" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if kill -0 "${METRICS_PID}" 2>/dev/null; then
            log "Metrics process did not exit; sending SIGKILL"
            kill -KILL "${METRICS_PID}" 2>/dev/null || true
        fi
    fi

    stop_container() {
        local name="$1"
        local role="$2"
        if ! docker ps -a -q -f "name=^${name}$" | grep -q .; then
            return
        fi
        if docker ps -q -f "name=^${name}$" | grep -q .; then
            # SIGINT is what Ctrl+C in a terminal sends. That's what `ros2 launch`
            # handles for graceful shutdown (it propagates the interrupt to every
            # child node, which then runs their lifecycle cleanup hooks).
            # tini (from --init) forwards SIGINT from PID 1 to the actual ros2 launch
            # process, which Python's signal handling otherwise blocks for PID 1.
            log "Stopping ${role} container ${name} (SIGINT, grace ${SHUTDOWN_GRACE_SEC}s)"
            docker stop --signal=SIGINT --time="${SHUTDOWN_GRACE_SEC}" "${name}" >/dev/null 2>&1 || true
            if docker ps -q -f "name=^${name}$" | grep -q .; then
                log "${role} container ${name} did not stop in grace period; forcing kill"
                docker kill "${name}" >/dev/null 2>&1 || true
            fi
        fi
        # Capture full stdout/stderr after the container has stopped
        local log_file="${RUN_DIR}/${role}_stdout.log"
        docker logs "${name}" > "${log_file}" 2>&1 || true
        docker rm -f "${name}" >/dev/null 2>&1 || true
    }

    if [[ "${VLM_LAUNCHED}" -eq 1 ]]; then
        stop_container "${VLM_NAME}" "vlm"
    fi
    if [[ "${AUTONOMY_LAUNCHED}" -eq 1 ]]; then
        stop_container "${AUTONOMY_NAME}" "autonomy"
    fi

    log "Run artifacts:"
    log "  ${RUN_DIR}"
    if [[ -d "${RUN_DIR}" ]]; then
        ls -la "${RUN_DIR}" || true
    fi
}

trap cleanup EXIT INT TERM

# -----------------------------------------------------------------------------
# Preflight checks on correct run environment
# -----------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not on PATH" >&2
    exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
    log "WARNING: DISPLAY is unset; visualization tools (RViz) will not appear on host"
fi

# Cyclone DDS (configured in the autonomy image) requests a 10MB socket receive buffer.
CYCLONE_RMEM_MIN=10485760
RMEM_MAX=$(cat /proc/sys/net/core/rmem_max 2>/dev/null || echo 0)
if (( RMEM_MAX < CYCLONE_RMEM_MIN )); then
    log "ERROR: net.core.rmem_max=${RMEM_MAX}, but Cyclone DDS requires >= ${CYCLONE_RMEM_MIN} (10MB)."
    log "       The autonomy container will fail to create a ROS 2 node. Fix on the host with:"
    log "           sudo sysctl -w net.core.rmem_max=2147483647"
    log "           sudo sysctl -w net.core.wmem_max=2147483647"
    log "       To persist across reboots, write the same key=value pairs into /etc/sysctl.d/10-cyclone.conf"
    exit 1
fi

mkdir -p "${LOG_PARENT_DIR}"
RUN_DIR="$(realpath "${LOG_PARENT_DIR}")/run_${RUN_TIMESTAMP}"
mkdir -p "${RUN_DIR}/ros"

log "Benchmark run starting"
log "  RUN_DIR=${RUN_DIR}"
log "  AUTONOMY_IMAGE=${AUTONOMY_IMAGE}"
log "  VLM_IMAGE=${VLM_IMAGE:-<disabled>}"
log "  METRICS_SCRIPT=${METRICS_SCRIPT:-<disabled>}"
log "  BENCHMARK_DURATION_SEC=${BENCHMARK_DURATION_SEC}"

# -----------------------------------------------------------------------------
# Launch autonomy container
# -----------------------------------------------------------------------------

XAUTH_PATH="${XAUTHORITY:-${HOME}/.Xauthority}"

log "Launching autonomy container ${AUTONOMY_NAME}"
docker run -d --init \
    --name "${AUTONOMY_NAME}" \
    --net=host --ipc=host --privileged \
    --shm-size=2g \
    --env "DISPLAY=${DISPLAY:-}" \
    --env "QT_X11_NO_MITSHM=1" \
    --volume "${XAUTH_PATH}:/root/.Xauthority:ro" \
    --volume "/tmp/.X11-unix:/tmp/.X11-unix:rw" \
    --volume "${RUN_DIR}/ros:/root/.ros/log" \
    "${AUTONOMY_IMAGE}" >/dev/null
AUTONOMY_LAUNCHED=1

# -----------------------------------------------------------------------------
# Launch VLM container (optional)
# -----------------------------------------------------------------------------

if [[ -n "${VLM_IMAGE}" ]]; then
    log "Launching VLM container ${VLM_NAME}"
    docker run -d --init \
        --name "${VLM_NAME}" \
        --net=host --ipc=host --privileged \
        --shm-size=2g \
        --env "DISPLAY=${DISPLAY:-}" \
        --env "QT_X11_NO_MITSHM=1" \
        --volume "${XAUTH_PATH}:/root/.Xauthority:ro" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix:rw" \
        --volume "${RUN_DIR}/ros:/root/.ros/log" \
        "${VLM_IMAGE}" >/dev/null
    VLM_LAUNCHED=1
fi

# -----------------------------------------------------------------------------
# Wait for liveness
# -----------------------------------------------------------------------------

log "Waiting ${STARTUP_WAIT_SEC}s for containers to come up"
sleep "${STARTUP_WAIT_SEC}"

check_running() {
    local name="$1"
    local state
    state="$(docker inspect -f '{{.State.Running}}' "${name}" 2>/dev/null || echo "false")"
    [[ "${state}" == "true" ]]
}

dump_container_logs() {
    local name="$1"
    log "Last 40 lines of ${name} stdout/stderr:"
    docker logs --tail 40 "${name}" 2>&1 | sed "s/^/    /" || true
}

if ! check_running "${AUTONOMY_NAME}"; then
    log "ERROR: autonomy container ${AUTONOMY_NAME} is not running after startup wait"
    dump_container_logs "${AUTONOMY_NAME}"
    exit 1
fi
if [[ "${VLM_LAUNCHED}" -eq 1 ]] && ! check_running "${VLM_NAME}"; then
    log "ERROR: VLM container ${VLM_NAME} is not running after startup wait"
    dump_container_logs "${VLM_NAME}"
    exit 1
fi

# -----------------------------------------------------------------------------
# Start metrics capture (optional)
# -----------------------------------------------------------------------------

if [[ -n "${METRICS_SCRIPT}" ]]; then
    if [[ ! -x "${METRICS_SCRIPT}" ]]; then
        log "ERROR: METRICS_SCRIPT='${METRICS_SCRIPT}' is not executable"
        exit 1
    fi
    log "Starting metrics capture: ${METRICS_SCRIPT}"
    "${METRICS_SCRIPT}" "${RUN_DIR}" "${BENCHMARK_DURATION_SEC}" \
        > "${RUN_DIR}/metrics.stdout" 2>&1 &
    METRICS_PID=$!
    log "Metrics capture pid: ${METRICS_PID}"
fi

# -----------------------------------------------------------------------------
# Benchmark loop
# -----------------------------------------------------------------------------

START_TIME=$(date +%s)
END_TIME=$((START_TIME + BENCHMARK_DURATION_SEC))

log "Benchmark running for ${BENCHMARK_DURATION_SEC}s (until $(date -d "@${END_TIME}" '+%Y-%m-%d %H:%M:%S'))"

while :; do
    now=$(date +%s)
    if (( now >= END_TIME )); then
        break
    fi

    remaining=$((END_TIME - now))
    sleep_for=$STATUS_LOG_INTERVAL_SEC
    if (( sleep_for > remaining )); then
        sleep_for=$remaining
    fi
    sleep "${sleep_for}"

    now=$(date +%s)
    elapsed=$((now - START_TIME))
    eta=$((END_TIME - now))
    if (( eta < 0 )); then eta=0; fi

    log "Benchmark running — elapsed $(fmt_duration ${elapsed}) / $(fmt_duration ${BENCHMARK_DURATION_SEC}), ETA $(fmt_duration ${eta})"

    if ! check_running "${AUTONOMY_NAME}"; then
        log "ERROR: autonomy container died mid-run"
        dump_container_logs "${AUTONOMY_NAME}"
        exit 1
    fi
    if [[ "${VLM_LAUNCHED}" -eq 1 ]] && ! check_running "${VLM_NAME}"; then
        log "ERROR: VLM container died mid-run"
        dump_container_logs "${VLM_NAME}"
        exit 1
    fi
done

log "Benchmark duration reached; tearing down"
# cleanup() runs on EXIT
