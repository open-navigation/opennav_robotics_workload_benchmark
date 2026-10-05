# opennav_benchmark_pipeline

Orchestrates a benchmark experiment across one or two Docker containers (an autonomy / AMR workload and an optional AI workload) plus an optional host-side system-metrics capture script to measure performance and resource utilization.

The [Practitioners Guide](../docs/practitioners_guide.md) may be of interest for those reading this far in detail looking to reproduce or test their own platforms.

## Host prerequisites

Setting up a platform from scratch (flashing/OS, GPU drivers, container runtime, and building the VLM inference image) is documented per platform under [`docs/platform_setup/`](../docs/platform_setup/): [`jetson_orin.md`](../docs/platform_setup/jetson_orin.md), [`jetson_thor.md`](../docs/platform_setup/jetson_thor.md), [`amd_strix_halo.md`](../docs/platform_setup/amd_strix_halo.md).

You must raise `net.core.rmem_max` and `net.core.wmem_max` before the autonomy container will create a ROS 2 node. On Ubuntu the default is ~200KB which is not sufficient for large topics. To persist across reboots, drop those two lines (as `net.core.rmem_max=…`) into `/etc/sysctl.d/10-cyclone.conf`.

```bash
sudo sysctl -w net.core.rmem_max=2147483647
sudo sysctl -w net.core.wmem_max=2147483647
```

The autonomy image bakes a Cyclone DDS config in at build time. Two are shipped:
- `cyclonedds_localhost.xml` DDS bound to loopback. Single-machine usage for running simulation on the same benchmarking platform.
- `cyclonedds_hil.xml` DDS bound to a LAN subnet (10.2.1.0, by default). Cross-machine HIL (simulator on machine A, benchmark on machine B).

Change to what is appropriate for your situation in the Dockerfiles. If doing HIL testing, use that XML putting the subnet as the static IP range used on the LAN in your setup.

## Parameters

| Var | Default | Purpose |
|---|---|---|
| `AUTONOMY_IMAGE` | `opennav_benchmark/robotic_amr_workload:jazzy` | Autonomy workload image. |
| `VLM_IMAGE` | `""` | If non-empty, also launches a VLM container from this image with tag belonging to the platform under benchmark (i.e. `jetson_thor`, `amd_strix_halo`, `jetson_orin`). |
| `METRICS_SCRIPT` | `"capture_system_metrics.py"` | If non-empty, runs this executable on the host during the benchmark. |
| `BENCHMARK_DURATION_SEC` | `1800` | How long to hold the benchmark before tearing down. |
| `STARTUP_WAIT_SEC` | `20` | Seconds to wait after launching containers before starting to record metrics. |
| `SHUTDOWN_GRACE_SEC` | `15` | SIGTERM grace period before `docker stop` escalates to SIGKILL. |
| `LOG_PARENT_DIR` | `./opennav_benchmark_logs` | Where the logs are created. |

## Build & run the simulation

```bash
cd /path/to/opennav_robotics_workload_benchmark
docker build -t opennav_benchmark/robotic_amr_simulation:jazzy \
  -f opennav_benchmark_pipeline/docker/robotic_amr_simulation/Dockerfile .
```

The orchestrator (`run_benchmark.sh`) only launches the autonomy and VLM containers; the simulator is started separately so it can be run on another machine or cloud server to avoid adding load to the benchmark host.

```bash
./opennav_benchmark_pipeline/run_simulation.sh
```

This runs a simplified gazebo model where rows and pallets are represented by simple boxes to enable real-time performance on typical workstation-class hardware for a 200,000 sqft facility. The simulation publishes the same ROS topics as the full mesh-based simulation, so the autonomy workload can be run against either.

If you want to run the simulator in the cloud consider using the full simulation using meshes of the warehouse environment with tens of thousands of models:

```bash
# Heavy mesh-based world for cloud server-class CPUs (slow):
./opennav_benchmark_pipeline/run_simulation.sh \
  ros2 launch opennav_benchmark_sim simulation.launch.py headless:=false

# Headless (no GUI, no RViz host requirements):
./opennav_benchmark_pipeline/run_simulation.sh \
  ros2 launch opennav_benchmark_sim simulation_simplified.launch.py headless:=true use_rviz:=false
```

The script `run_simulation.sh` will automatically not launch rviz or the gazebo client when over SSH for your convenience.

## Build & run the VLM (optional)

The AI workload (VLM) is packaged separately for each benchmark platform under `docker/ai_workload/`. Build the Dockerfile matching the platform under test and tag it with that platform's name, so the orchestrator can resolve the matching run-flag profile from the tag suffix:

```bash
cd /path/to/opennav_robotics_workload_benchmark

# Tag suffix = the platform directory under docker/ai_workload/:
#   jetson_orin, jetson_thor, amd_strix_halo, jetson_thor_optimized
docker build -t opennav_benchmark/ai_workload:amd_strix_halo \
  -f opennav_benchmark_pipeline/docker/ai_workload/amd_strix_halo/Dockerfile .
```

You can test it via:

```bash
./opennav_benchmark_pipeline/run_vlm.sh opennav_benchmark/ai_workload:amd_strix_halo  # jetson_orin, jetson_thor, amd_strix_halo, jetson_thor_optimized
```

Each platform directory also ships a `profile.sh` capturing the extra `docker run` flags that platform needs (GPU runtime, device passthrough, etc.). 

## Build & run the benchmark

```bash
cd /path/to/opennav_robotics_workload_benchmark
docker build -t opennav_benchmark/robotic_amr_workload:jazzy \
  -f opennav_benchmark_pipeline/docker/robotic_amr_workload/Dockerfile .
```

This builds the project's AMR workload, processing the multitude of sensor data, planning, control, autonomy and the mission task dispatcher as if running with physical hardware. The navigation setup can be found in `opennav_benchmark_nav` and the autonomy application in `opennav_benchmark_mission_dispatcher`

Run the following command:

```bash
cd /path/to/opennav_robotics_workload_benchmark
./opennav_benchmark_pipeline/run_benchmark.sh
```

Each run produces logs from the benchmark autonomy workload / VLM / metrics in the directory `opennav_benchmark_logs/run_<unix_ts>`. This can be used to analyze the captured metrics, AI output, and autonomy logs (such as with the `opennav_benchmark_analysis` directory).

The benchmark orchestrator only launches the VLM container when `VLM_IMAGE` is set; it derives the profile from the tag suffix (`amd_strix_halo` here) and applies those flags. Set it in the `run_benchmark.sh` script or pass it on the command line:

```bash
cd /path/to/opennav_robotics_workload_benchmark
VLM_IMAGE=opennav_benchmark/ai_workload:amd_strix_halo ./opennav_benchmark_pipeline/run_benchmark.sh  # replace tags with jetson_orin, jetson_thor, jetson_thor_optimized
```

For ad-hoc runs, you can launch the autonomy workload container by hand without the rest of the benchmark:

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

## Running the analysis

To analyze a single benchmark run, pass its `system_metrics_<timestamp>.json` file to the single-run script:

```bash
cd /path/to/opennav_robotics_workload_benchmark
python opennav_benchmark_analysis/analyze_single_run.py \
  opennav_benchmark_logs/run_<unix_ts>/system_metrics.json \
  --output-dir ./output
```

This generates interactive Plotly charts (CPU, GPU, RAM, thermals, I/O, etc.) and an HTML report under `output/run_<unix_ts>/report.html`.

### Cross-platform comparison (all 3 platforms)

To compare benchmark results across the AMD Strix Halo, NVIDIA Jetson Orin, and NVIDIA Jetson Thor platforms, provide each platform's metrics file:

```bash
cd /path/to/opennav_robotics_workload_benchmark
python opennav_benchmark_analysis/compare_platforms.py \
  --amd  opennav_benchmark_logs/run_<amd_ts>/system_metrics.json \
  --orin opennav_benchmark_logs/run_<orin_ts>/system_metrics.json \
  --thor opennav_benchmark_logs/run_<thor_ts>/system_metrics.json \
  --output-dir ./output
```

This generates side-by-side comparison charts (resource headroom, compute efficiency, thermals, power-per-watt, radar plots, etc.) and an HTML report at `output/comparison/report.html`.
