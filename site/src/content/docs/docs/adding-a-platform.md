---
title: Adding a platform
description: "How to bring a new compute platform into the benchmark: the code to write, the measurements to take, and what a submitted result must contain."
---

The benchmark is built to be extended. Adding a platform is four pieces of work: program the
pipeline to recognize and instrument your hardware platform, give it an AI workload container,
measure your sensor-driver load, and run the matrix.

If you are a hardware vendor and want your platform to be included in the next revision of the
technical report, see [hardware vendors](/opennav_robotics_workload_benchmark/about#vendors).

## 1. Hardware platform metrics capture

All three changes are in `opennav_benchmark_pipeline/scripts/hardware_platforms.py`.

**Detection.** Extend `detect_platform()` so it returns your platform key. The existing
implementation reads `/proc/device-tree/model`, then `/etc/nv_tegra_release`, then
`/proc/cpuinfo`. Add whatever identifies your board, and return a stable snake_case key.

**Sensor-driver profile.** Add a `HARDWARE_PROFILES` entry keyed by that platform key:

```python
HARDWARE_PROFILES = {
    # ...
    'your_platform': {
        'lidar_3d': 0.00,      # fraction of one core, per instance
        'lidar_2d': 0.00,
        'rgbd_camera': 0.00,
    },
}
```

Do not guess these. See step 3.

**GPU metrics.** Subclass `GpuMetrics` and implement `collect()`, returning whichever of these
your platform exposes: `gpu_util`, `gpu_clock_mhz`, `gpu_mem_clock_mhz`, `gpu_mem_used_mb`,
`gpu_mem_total_mb`, `gpu_temp`, `gpu_power_w`, `board_power_w`, `npu_util`,
`mem_bandwidth_gbps`. `AmdGpuMetrics` (ROCm sysfs, DPM clocks, VCN, XDNA) and
`JetsonGpuMetrics` (tegrastats, NVML, power rails) are the two worked examples. Return only
what you can actually read. The analysis handles absent metrics, but a fabricated one poisons
every comparison it appears in.

## 2. Add the AI workload container

Create `opennav_benchmark_pipeline/docker/ai_workload/<your_platform>/` with:

- a `Dockerfile` that builds a llama.cpp server with your platform's GPU acceleration and
  serves `ggml-org/gemma-4-31B-it-GGUF:Q4_K_M` on `http://localhost:8080/v1`
- a `profile.sh` containing the extra `docker run` flags your platform needs, such as the GPU
  runtime and device passthrough

The existing `amd_strix_halo`, `jetson_orin`, and `jetson_thor` directories are the templates.

## 3. Measure your sensor-driver load

The benchmark simulates sensors, but driver CPU cost is real and platform-specific, so it is
measured on hardware and replayed. Attach real sensors, run each driver at the rate in the
[methodology](/opennav_robotics_workload_benchmark/methodology#sensors), and record steady-state
CPU as a fraction of one core per instance. The published coefficients came from Orbbec Gemini
355 depth cameras and Ouster OS-1 32 lidars.

Using another platform's coefficients, or estimating them, invalidates the comparison. This
measurement is the single most common thing to get wrong.

## 4. Run the matrix

For each power mode you want represented:

```bash
# developer machine
./run_simulation.sh

# platform under test
BENCHMARK_DURATION_SEC=900 \
VLM_IMAGE=opennav_benchmark/ai_workload:<your_platform> \
./run_benchmark.sh
```

Follow the [practitioner's guide](/opennav_robotics_workload_benchmark/docs/reproduce) for the
network and DDS setup. Results land in `opennav_benchmark_logs/`.

## 5. Submit

Open a pull request with the complete
`opennav_benchmark_logs/<category>/<platform>/` tree. A result can be published when it has:

- a complete `system_metrics.json` covering the whole run
- the full `ros/` log directory, since missions, control-loop misses, planner cycle times, and
  VLM outcomes are all parsed from it
- the configured TDP, and firmware and BIOS versions
- the simulation machine's specification
- any vendor relationship disclosed

Then add a `Category` entry (or a `RunSpec` inside an existing one) in
`opennav_benchmark_analysis/export_site_data.py`, run `make site-data` from the repository root,
and include the regenerated `site/src/data` and `site/public/data` in the same pull request. CI
re-exports the dataset and fails if the committed copy does not match, and it fails too if a run
directory has no `RunSpec` declaring it.

That is the only change the website needs, because every route, selector, and chart is generated
from the exported data.
