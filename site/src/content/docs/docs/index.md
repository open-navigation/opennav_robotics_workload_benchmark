---
title: Running the benchmark
description: Documentation for running Open Navigation's robotics workload benchmark on your own hardware, and for adding a new compute platform to it.
---

These pages instruct you how to run this yourself on the provided platforms for reproduction
and additional platforms for further comparison. See
[results](/opennav_robotics_workload_benchmark/results) and
[platform comparison](/opennav_robotics_workload_benchmark/platforms) pages for benchmark
evaluations.

## What you need

Two machines on a wired network:

- **A developer or external machine** running the Gazebo warehouse simulation and the robot's
  simulated sensors in a Docker container. Keeping the simulation off the machine being measured
  is what makes the utilization numbers represent the run-time deployed application load.
- **The compute platform under test**, running the AMR autonomy container, the AI workload
  container, the simulated sensor-driver load, and the metrics capture script.

DDS is restricted to the wired Ethernet interface so discovery traffic and interference stay
out of the measurement.

## Where to start

| If you want to… | Go to |
| --- | --- |
| Reproduce the published results | [Run the benchmark](/opennav_robotics_workload_benchmark/docs/reproduce) |
| Configure a specific platform | [Platform setup](/opennav_robotics_workload_benchmark/docs/platform-setup/amd-strix-halo) |
| Benchmark new platforms | [Adding a platform](/opennav_robotics_workload_benchmark/docs/adding-a-platform) |
