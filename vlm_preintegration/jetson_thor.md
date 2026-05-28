# NVIDIA Jetson Thor: Gemma-4 31B VLM Setup & Runtime

Serve Gemma-4 31B as an OpenAI-compatible VLM endpoint on the Jetson Thor using
llama.cpp (NVIDIA's prebuilt Jetson container, CUDA backend). The server listens on
`http://localhost:8080/v1`, which the benchmark's
[`vlm_params.yaml`](../opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml)
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

---

**Stop here if setting up for the benchmark pipeline. Below this is a full-setup for the VLM which may be useful outside of the context of the benchmark. See the pipieline's `README.md` for instructions for building the containers for the benchmark.**

---

## 3. Build the Server Image

From this directory ([`vlm_preintegration/`](.)):

```bash
docker build -f Dockerfile.thor -t opennav-vlm-thor .
```

> Container tag: [`Dockerfile.thor`](Dockerfile.thor) uses NVIDIA's Thor-specific
> `llama_cpp:latest-jetson-thor` image.

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

## 4. Run the Server

Launch the model server directly from NVIDIA's prebuilt container (it serves on `:8080`):

```bash
docker run -it --rm --runtime=nvidia --network host \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-thor \
  llama-server -hf ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
```

The bundled [`Dockerfile.thor`](Dockerfile.thor) bakes this same `llama-server` invocation,
so you can alternatively build it (section 4) and run with the same runtime/cache flags:

```bash
docker run --rm -it --runtime=nvidia --network host \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  opennav-vlm-thor
```

---

## 5. Verify

First call blocks while the model downloads and loads; subsequent calls are fast.

```bash
# List served models
curl http://localhost:8080/v1/models

# Text smoke test
curl http://localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma-4","messages":[{"role":"user","content":"Write a poem about the Kraken."}]}'
```

For a vision (VLM) check, send an image with the warehouse prompt
(`docs/warehouse_prompt.txt`) via an `image_url` content block to confirm the `mmproj`
path is active.

---

## Further Reading

- [Jetson AI Lab: LLM/VLM Models & Containers](https://www.jetson-ai-lab.com/models/)
- [NVIDIA SDK Manager: Jetson Flashing](https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation)
- [Jetson AGX Thor Devkit: Docker setup](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html)
- [Jetson AGX Thor Devkit: CUDA setup](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_cuda.html)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
- [ggml-org/gemma-4-31B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF)
