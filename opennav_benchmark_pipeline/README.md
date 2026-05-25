# opennav_benchmark_pipeline

Orchestrates a benchmark experiment across one or two Docker containers (an autonomy / AMR workload and an optional VLM) plus an optional host-side system-metrics capture script. Collects `~/.ros/log` from each container into a timestamped host directory so artifacts survive container teardown.

## Layout

```
opennav_benchmark_pipeline/
├── README.md
├── run_benchmark.sh                  # the orchestrator
└── docker/
    ├── robotic_amr_workload/
    │   ├── Dockerfile                # builds & launches the application workspace (mission runner + Nav2 + VLM)
    │   ├── entrypoint.sh             # sources /opt/ros/jazzy + the workspace overlay before exec'ing CMD
    │   ├── cyclonedds_localhost.xml  # Cyclone DDS bound to loopback — single-machine default (host shares lo with containers via --net=host)
    │   └── cyclonedds_hil.xml        # Cyclone DDS bound to a LAN subnet — for HIL (sim on machine A, autonomy on machine B)
    └── robotic_amr_simulation/
        ├── Dockerfile                # builds & launches the lightweight simplified Gazebo world (box-primitive warehouse) with GUI
        ├── entrypoint.sh             # sources /opt/ros/jazzy + the workspace overlay before exec'ing CMD
        ├── cyclonedds_localhost.xml  # same loopback DDS config — pairs the sim with a workload container on the same host
        └── cyclonedds_hil.xml        # LAN DDS config — sim on machine A, autonomy on machine B
```

The `robotic_amr_workload/` Dockerfile bundles the application workspace, resolves its dependencies via `rosdep`, builds it with `colcon`, and launches `opennav_benchmark_application/benchmark_application.launch.py` on container start (mission runner + Nav2 + VLM). The orchestrator is workload-agnostic — it never passes a command, it just runs whatever the image's `CMD` defines.

## Host prerequisites

The autonomy image pins RMW to Cyclone DDS and the bundled config requests a 10MB socket receive buffer. That's a host kernel setting — Docker can't change it from inside the container — so you must raise `net.core.rmem_max` (and the matching send buffer) before the autonomy container will create a ROS 2 node. On Ubuntu the default is ~200KB.

```bash
sudo sysctl -w net.core.rmem_max=2147483647
sudo sysctl -w net.core.wmem_max=2147483647
```

To persist across reboots, drop those two lines (as `net.core.rmem_max=…`) into `/etc/sysctl.d/10-cyclone.conf`. `run_benchmark.sh` preflight-checks this and aborts with a clear error if the value is too low.

**For HIL setups, the same `sysctl` bump must be applied on every machine** participating in the DDS domain, not only the one running `run_benchmark.sh`.

## Build the autonomy image

The image bundles the application workspace (`opennav_benchmark_application`, `opennav_benchmark_nav2`, `opennav_benchmark_robot`, `opennav_benchmark_vlm`, `opennav_benchmark_vlm_msgs`), resolves their ROS / system dependencies with `rosdep`, builds with `colcon`, and launches `benchmark_application.launch.py` on container start.

The **build context must be the repo root** so the Dockerfile can COPY the package directories. Run from `opennav_robotics_workload_benchmark/`:

```bash
cd /path/to/opennav_robotics_workload_benchmark
docker build -t opennav_benchmark/robotic_amr_workload:jazzy \
  -f opennav_benchmark_pipeline/docker/robotic_amr_workload/Dockerfile .
```

The trailing `.` is the build context (the repo root). Rebuild any time you change source under one of the bundled packages, or change the Cyclone DDS config.

The orchestrator mounts `$XAUTHORITY` and `/tmp/.X11-unix` into the container, which is usually enough for RViz to appear on the host. If it doesn't, run `xhost +local:root` once per session to allow local root clients.

### Localhost vs HIL DDS config

The autonomy image bakes a Cyclone DDS config in at build time. Two are shipped:

- `cyclonedds_localhost.xml` (**default**) — DDS bound to loopback. Single-machine usage.
- `cyclonedds_hil.xml` — DDS bound to a LAN subnet. Cross-machine HIL (simulator on machine A, autonomy on machine B).

To switch to HIL:
1. Edit `docker/robotic_amr_workload/cyclonedds_hil.xml` and set `<NetworkInterface address="…">` to your LAN subnet (e.g. `192.168.1.0`).
2. In `docker/robotic_amr_workload/Dockerfile`, change `COPY cyclonedds_localhost.xml …` to `COPY cyclonedds_hil.xml …`.
3. Rebuild the image on **both** machines (same Dockerfile and xml on each).
4. Confirm the `sysctl` bump (above) is applied on **both** machines.

## Build the simulation image

The `robotic_amr_simulation/` image bundles `opennav_benchmark_sim` + `opennav_benchmark_robot`, installs Gazebo Harmonic via `ros-jazzy-ros-gz*`, and on container start launches `simulation_simplified.launch.py` with `headless:=false` — the box-primitive warehouse world (`benchmark_warehouse_simplified.sdf.xacro`) plus the Gazebo GUI client and RViz. The simplified world replaces every mesh-based shelf/pallet/person/forklift with appropriately sized boxes so the scene runs real-time; the heavy mesh-based world (`benchmark_warehouse.sdf.xacro`) is still installed in the image if you want to launch it manually.

Build context is the **repo root**, same as the autonomy image:

```bash
cd /path/to/opennav_robotics_workload_benchmark
docker build -t opennav_benchmark/robotic_amr_simulation:jazzy \
  -f opennav_benchmark_pipeline/docker/robotic_amr_simulation/Dockerfile .
```

The image bakes in the same `cyclonedds_localhost.xml` as the autonomy image (loopback discovery), so on a single host the two containers find each other automatically when both run with `--net=host`. Switching to HIL follows the identical recipe from the "Localhost vs HIL DDS config" section — edit the xml in `docker/robotic_amr_simulation/` and rebuild.

## Run the simulation

The orchestrator (`run_benchmark.sh`) only launches the autonomy and VLM containers; the simulator is started separately so you can keep the sim running across multiple benchmark runs (it takes a few seconds to come up). Start it once, then run the orchestrator as many times as you want against the same sim.

The image renders a Gazebo GUI plus RViz, so X11 forwarding is required. The sim runs **attached** (not detached) so its stdout/stderr is visible in your terminal and Ctrl+C tears it down cleanly. Open a dedicated terminal for it; in another terminal you run the benchmark orchestrator.

```bash
./opennav_benchmark_pipeline/run_simulation.sh
```

`run_simulation.sh` is a thin wrapper around `docker run` that sets the network/X11/IPC/`--init` flags. Override the image with `SIM_IMAGE=...`, override the container name with `SIM_NAME=...`, or append a custom CMD after the script name (passed through to docker):

```bash
# Heavy mesh-based world (slow):
./opennav_benchmark_pipeline/run_simulation.sh \
  ros2 launch opennav_benchmark_sim simulation.launch.py headless:=false

# Headless (no GUI, no RViz host requirements):
./opennav_benchmark_pipeline/run_simulation.sh \
  ros2 launch opennav_benchmark_sim simulation_simplified.launch.py headless:=true use_rviz:=false
```

The Gazebo GUI and RViz windows should appear within ~10–15 s. **Hit `Ctrl+C` in this terminal to stop the sim** — that sends SIGINT to `ros2 launch` which runs the graceful shutdown path, and `--rm` deletes the container on exit. If a stuck process keeps it alive, hit Ctrl+C again or open another terminal and run `docker kill opennav_sim`.

## Run the workload directly

For ad-hoc runs (no benchmark timing, no metrics capture, no automated teardown) you can launch the autonomy/workload container by hand. Open a second terminal alongside the simulation:

```bash
docker run --rm -it --init \
  --name opennav_workload \
  --net=host --ipc=host --privileged \
  --shm-size=2g \
  --env "DISPLAY=${DISPLAY}" \
  --env "QT_X11_NO_MITSHM=1" \
  --volume "${XAUTHORITY:-$HOME/.Xauthority}:/root/.Xauthority:ro" \
  --volume "/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  opennav_benchmark/robotic_amr_workload:jazzy
```

The image's `CMD` runs `benchmark_application.launch.py` (mission runner + Nav2 + VLM). Hit `Ctrl+C` to stop; `--rm` deletes the container on exit. To capture ROS logs, add `--volume "$(pwd)/opennav_benchmark_logs/manual:/root/.ros/log"` before the image name.

## Run the benchmark

Run from the **repo root** so the relative log dir lands somewhere predictable:

```bash
cd /path/to/opennav_robotics_workload_benchmark
./opennav_benchmark_pipeline/run_benchmark.sh
```

The script writes its output to `${LOG_PARENT_DIR}/run_<unix_ts>/`, and `LOG_PARENT_DIR` defaults to `./opennav_benchmark_logs` (relative to your current shell). Running from the repo root therefore produces `<repo>/opennav_benchmark_logs/run_<ts>/`. Override `LOG_PARENT_DIR` to put it anywhere else.

Edit the parameter block at the top of `run_benchmark.sh`, or override per-run via env vars:

```bash
BENCHMARK_DURATION_SEC=60 ./opennav_benchmark_pipeline/run_benchmark.sh
VLM_IMAGE=my/vlm:latest ./opennav_benchmark_pipeline/run_benchmark.sh
METRICS_SCRIPT=/abs/path/to/capture.sh ./opennav_benchmark_pipeline/run_benchmark.sh
```

## Parameters

| Var | Default | Purpose |
|---|---|---|
| `AUTONOMY_IMAGE` | `opennav_benchmark/robotic_amr_workload:jazzy` | Autonomy workload image. Its `CMD`/`ENTRYPOINT` brings up the workload — orchestrator passes no command. |
| `VLM_IMAGE` | `""` | If non-empty, also launches a VLM container from this image. Empty disables. |
| `METRICS_SCRIPT` | `""` | If non-empty, runs this executable on the host during the benchmark. Invoked as `<script> <run_dir> <duration_sec>` — your script writes its output files directly into `<run_dir>`. Empty disables. |
| `BENCHMARK_DURATION_SEC` | `180` | How long to hold the benchmark before tearing down. |
| `STARTUP_WAIT_SEC` | `20` | Seconds to wait after launching containers before starting the timer. |
| `STATUS_LOG_INTERVAL_SEC` | `30` | Period for the "still running, ETA …" status logs. |
| `SHUTDOWN_GRACE_SEC` | `15` | SIGTERM grace period before `docker stop` escalates to SIGKILL. |
| `LOG_PARENT_DIR` | `./opennav_benchmark_logs` | Where the timestamped run dir is created. |

## Output

Each run produces:

```
opennav_benchmark_logs/run_<unix_ts>/
├── ros/                              # /root/.ros/log from both containers (autonomy + VLM if enabled);
│                                     # ROS gives each launch its own subdir (launch_<ts>_<pid>/), so they don't collide
├── metrics.stdout                    # (only if METRICS_SCRIPT was set) stdout/stderr of the metrics script
└── ...                               # any other files METRICS_SCRIPT writes into run_<ts>/
```

The absolute path is echoed at the start of every run and again on exit.

**Logs are root-owned.** Because the containers run as root and write through a bind mount, the resulting host files are root-owned. Use `sudo rm -rf <run_dir>` or `sudo chown -R "$(id -u):$(id -g)" <run_dir>` if you need to clean up or edit them.

## DDS / discovery

The provided Dockerfile pins RMW to Cyclone DDS. By default it bakes in `cyclonedds_localhost.xml`, which binds DDS to loopback (`127.0.0.1`); because the orchestrator launches every container with `--net=host`, the host and all containers share the same network namespace — including loopback — so the localhost config gives full host ↔ container ↔ container discovery with no external traffic. For HIL, swap in `cyclonedds_hil.xml` per the "Localhost vs HIL DDS config" section above.

**For operator-supplied VLM images**, the same RMW + Cyclone DDS config is required to participate in discovery. Either:
- bake `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` and the same `CYCLONEDDS_URI` into your VLM image, or
- mount the same Cyclone xml and set the env vars at container launch.

## Verification scenarios

1. **Happy path** — build the image, `xhost +local:root`, run with defaults. RViz should appear; the benchmark logs ETA every 30s; after the duration the container stops cleanly; logs land in `opennav_benchmark_logs/run_<ts>/`.
2. **Force-kill path** — start a run, then `kill -STOP $(docker inspect -f '{{.State.Pid}}' opennav_autonomy_<ts>)` from another terminal so the container ignores SIGTERM. Confirm the orchestrator falls back to `docker kill` after `SHUTDOWN_GRACE_SEC`.
3. **Ctrl-C path** — start a run, hit Ctrl-C mid-benchmark. Containers should still tear down and the run dir should still contain partial logs.
