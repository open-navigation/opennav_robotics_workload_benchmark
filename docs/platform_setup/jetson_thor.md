# NVIDIA Jetson Thor: Gemma-4 31B VLM Setup & Runtime

Serve Gemma-4 31B as an OpenAI-compatible VLM endpoint on the Jetson Thor using
llama.cpp (NVIDIA's prebuilt Jetson container, CUDA backend). The server listens on
`http://localhost:8080/v1`, which the benchmark's
[`vlm_params.yaml`](https://github.com/open-navigation/opennav_robotics_workload_benchmark/blob/main/opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml)
already targets out of the box.

> Benchmark note: All three platforms (AMD, Jetson Orin, Jetson Thor) run the
> *identical* model `ggml-org/gemma-4-31B-it-GGUF:Q4_K_M` through `llama-server`.
> Keep the model and quant identical across platforms for a valid 1:1 comparison.

---

## 1. Flash JetPack via NVIDIA SDK Manager

Flash JetPack from a host Ubuntu machine using the USB Debug/Flashing port:

- https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation

- Connect the Jetson to the host via the USB Debug/Flashing port.
- In SDK Manager, select Jetson Thor as the target.
- Choose the JetPack version and include CUDA, cuDNN, and TensorRT.
- Complete flashing and component installation.

Boot the Jetson, finish initial OS setup, then:

```bash
sudo apt-get update && sudo apt-get upgrade
```

> Thor uses a newer stack than Orin (newer JetPack/L4T, PyTorch `nv25.08` vs Orin's
> `nv25.02` in these notes). Use the Thor devkit guides for Docker + CUDA bring-up:
> [setup_docker](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html),
> [setup_cuda](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_cuda.html).

---

## 2. Install NVIDIA Container Toolkit

```bash
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Docs: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html

Verify GPU access from a container:

```bash
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

### Model Notes

- Model: `ggml-org/gemma-4-31B-it-GGUF` (multimodal, text + image). Default quant
  `Q4_K_M` (~18.7 GB) fits the Thor's large unified memory with plenty of headroom. (Only
  change the quant if you change it on every platform.)
- llama.cpp version: the `gemma4` architecture requires a recent llama.cpp build (the
  GGUF was produced with llama.cpp release ≈ `b8778`). If the server errors
  `unknown model architecture: 'gemma4'`, the container's llama.cpp is too old. Pull a
  newer `llama_cpp` Jetson image. (The technician hit this exact error running Gemma-4 on
  Thor via an older Ollama/llama.cpp build.)
- `llama-server -hf` downloads the GGUF and its vision projector (`mmproj`) into
  `LLAMA_CACHE` (set to `/root/.cache/huggingface` in the image). Mount
  `-v $HOME/.cache/huggingface:/root/.cache/huggingface` so the download persists.

Reference for Jetson LLM/VLM containers: https://www.jetson-ai-lab.com/models/

---

## Further Reading

- [Jetson AI Lab: LLM/VLM Models & Containers](https://www.jetson-ai-lab.com/models/)
- [NVIDIA SDK Manager: Jetson Flashing](https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation)
- [Jetson AGX Thor Devkit: Docker setup](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html)
- [Jetson AGX Thor Devkit: CUDA setup](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_cuda.html)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
- [ggml-org/gemma-4-31B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF)
