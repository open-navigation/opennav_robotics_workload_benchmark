# Open Navigation's Robotics Workload Benchmark

This is a robotics and AI workload benchmark to compare various hardware platforms using realistically complex, data intensive, representative applications. Many benchmarks exist from both hardware vendors and community members, but nearly all focus on evaluating a particular component or algorithm in isolation. Often times, multiple of these algorithms need to be run together which may interact negatively when composed into a full system due to sharing of limited CPU or accelerated computing resources (GPU, NPU, FPGA, etc). Other times, benchmarks that may consider a robotics system use trivialized workloads from basic simulation environments and sensor data sources which don't provide particularly insightful results for companies and industrial integrators. 

This project aims to fill the gap by providing a reproducable, independent benchmark for comparing and evaluating compute solutions for Robotics or Physical AI applications in all of their complexity. For this benchmark, we use Nav2 autonomously navigating a forklift material handling robot within a 200,000 sqft (18,600 m2) industrial warehouse environment to move pallets from shipping/receiving to shelving units, processing multiple 3D lidars, 2D safety lidars, RGBD cameras, and internal sensors. This workload is representative of dozens of companies and tends of thousands of robotics deployed today in production environments.

The benchmark also includes an (optional) Edge AI workload. We use Gemma 4.0, a popular Visual-Language Model (VLM), to exercise the platforms' GPUs during the benchmark session and integrate it into navigation for scene understanding and semantic context in the navigation behavior. We chose a LLM/VLM as robotics-targeted embedded platforms are being built with LLM/VLMs in mind & there is much interest in integrating them into robotics products. However, this could be easily replaced with another AI/GPU workload(s) (object detection, segmentation, RL, VLA, etc) simply by changing the AI workload Dockerfile. VLMs are extremely intensive so we feel they make a good benchmark case to fully leverage the capabilities of modern platforms.

We compare both system metrics as well as important performance analysis of the autonomous navigation and AI workload performance on each platform.

TODO video/gif of the robot / data / environment

⚠️ Need ROS 2, Nav2 help or support? Contact Open Navigation! ⚠️


# Platforms Evaluated

To add additional platforms, open a PR with your results and platform description!

## NVIDIA Jetson AGX Orin

The [Jetson AGX Orin](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/) is NVIDIA's established embedded AI platform widely adopted in robotics. It features 12 Arm Cortex-A78AE CPU cores at up to 2.2 GHz paired with a 2048-core Ampere GPU and 64 Tensor Cores. The module provides up to 275 INT8 TOPS (sparse) of AI performance, with two NVDLA 2.0 accelerators contributing roughly 40% of that total. It includes 64GB of unified LPDDR5 memory with 204.8 GB/s bandwidth across a 256-bit bus. Power is configurable from 15W to 60W (MAXN mode). The Orin is the current workhorse of many production robotics deployments and serves as our baseline platform.

## NVIDIA Jetson Thor

The [Jetson Thor](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-thor/) is NVIDIA's next-generation embedded AI module built on the Blackwell GPU architecture. It pairs 14 Arm Neoverse V3AE CPU cores at up to 2.6 GHz with 2560 CUDA cores and 96 fifth-generation Tensor Cores. Thor delivers up to 2070 FP4 TFLOPS (sparse) and over 1000 INT8 TOPS, representing a 7.5x AI performance increase over the AGX Orin. It includes 128GB of LPDDR5X memory at 4266 MHz with 273 GB/s bandwidth. Power is configurable from 40W to 130W. Thor is designed as the next platform for physical AI and advanced robotics applications.

## AMD X100 (Strix Halo)

The [Ryzen AI Max+ 395](https://www.amd.com/en/products/processors/laptop/ryzen/ai-300-series/amd-ryzen-ai-max-plus-395.html) is AMD's flagship APU targeting AI and edge workloads. It features 16 Zen 5 CPU cores (32 threads) boosting up to 5.1 GHz with 64MB L3 cache, paired with a 40 compute unit RDNA 3.5 integrated GPU delivering 59.4 FP16 TFLOPS and a dedicated XDNA 2 NPU providing 50 INT8 TOPS. It supports up to 128GB of unified LPDDR5X-8000 memory with 256 GB/s bandwidth, and AMD's Variable Graphics Memory technology allows up to 96GB to be allocated as VRAM. The configurable TDP ranges from 45W to 120W. The Strix Halo represents a compelling x86-based alternative to the Jetson ecosystem for robotics, offering strong CPU performance and a large unified memory pool for LLM/VLM workloads. Built on TSMC's 4nm process.

| Feature | Jetson AGX Orin | Jetson Thor | X100 / Strix Halo |
|---|---|---|---|
| **CPU** | 12x Arm Cortex-A78AE @ 2.2 GHz | 14x Arm Neoverse V3AE @ 2.6 GHz | 16x Zen 5 (32T) @ 5.1 GHz |
| **GPU Architecture** | Ampere | Blackwell | RDNA 3.5 |
| **GPU Cores** | 2048 CUDA + 64 Tensor | 2560 CUDA + 96 Tensor | 2560 Shaders (40 CUs) |
| **NPU / DLA** | 2x NVDLA 2.0 | DLA (105 INT8 TOPS) | XDNA 2 (50 TOPS) |
| **RAM** | 64 GB LPDDR5 | 128 GB LPDDR5X | Up to 128 GB LPDDR5X |
| **Memory Bandwidth** | 204.8 GB/s | 273 GB/s | 256 GB/s |
| **Power (TDP)** | 15–60 W | 40–130 W | 45–120 W |


# Architecture


# Simulation


(larger possible, but wanted to make sure could run realtime on reasonably modern laptops for more accessible reproduction... and 200k sqft is still pretty good)


# Robotic & AI Workloads

# Results

# Reproduction







 We do so to understand the performance of a robotics compute solution not just in individual benchmark tests about particular programs or algorithms but as a full, complex, and realistically laid out robotics product.

We provide the instructions and tooling to run a pipeline on a compute platform to capture system and workload metrics to benchmark and compare many common compute platforms. We principly do Jetson Orin, Jetson Thor, and AMD Ryzen AI Max+ 395 (Strix Halo, X100) as a viable competitor to the Jetsons for robotics applications. 

The robotics workload is a autonomous forklift robot with 3x 3D lidars, 2x 2D safety lidars, 3x depth cameras, as well as IMU. We'll show an image of this robot clearly with the data here. We then run this with Nav2 to autonomously navigate a 200,000 sqft (18.600 m2) with planning, control, perception, and autonomy behavior. We use the recent VLM model Gemma 4.0 to provide scene understanding and semantic context to the scene in the navigation behavior tree to impact navigation decisions and algorithm selection. This is a realistic system run on real warehouse logistics, material handling, and forklift style robots in production today. 

The readme will contain a video of the simulation running for the benchmark, rgraphics and analysis of the results for teh platforms, and include high level instructions (and point to the pipeline readme for more details). Also a diagram of the solution architecture.












# TODO Title

Description, intent, what it does
Diagram
Video of it running in simulation

Gif of the robot / data

Metrics analysis / graphs

Reproduction