# NVIDIA Jetson Orin AGX 64G: Gemma-4 31B VLM Setup & Runtime

Serve Gemma-4 31B as an OpenAI-compatible VLM endpoint on the Jetson Orin AGX 64G
using llama.cpp (NVIDIA's prebuilt Jetson container, CUDA backend). The server listens
on `http://localhost:8080/v1`, which the benchmark's
[`vlm_params.yaml`](../opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml)
already targets out of the box.

> Benchmark note: All three platforms (AMD, Jetson Orin, Jetson Thor) run the
> *identical* model `ggml-org/gemma-4-31B-it-GGUF:Q4_K_M` through `llama-server`.
> Keep the model and quant identical across platforms for a valid 1:1 comparison.

> Storage: The Orin AGX ships with limited onboard eMMC (64 GB). An additional NVMe
> SSD is required to hold the model and container storage; see step 2.

---

## 1. Flash JetPack via NVIDIA SDK Manager

Flash JetPack from a host Ubuntu machine using the USB Debug/Flashing port:

- https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation

- Connect the Jetson to the host via the USB Debug/Flashing port.
- In SDK Manager, select Jetson Orin AGX as the target.
- Choose the JetPack version and include CUDA, cuDNN, and TensorRT. These notes were
  produced with JetPack 6.2.2 (CUDA 12.6, cuDNN 9, TensorRT) on the AGX Orin.
- Complete flashing and component installation.

Boot the Jetson, finish initial OS setup, then:

```bash
sudo apt-get update && sudo apt-get upgrade
```

---

## 2. Provision NVMe Storage

The onboard eMMC is too small for a 31B model. Mount an NVMe SSD and relocate Docker's
data directory onto it:

- https://www.jetson-ai-lab.com/tutorials/ssd-docker-setup/

Key steps from the guide:
- Format and mount the NVMe SSD (e.g. at `/ssd`).
- Relocate the Docker data root (`/var/lib/docker`) onto the SSD mount.
- Verify Docker writes to the SSD before proceeding.

Create the data and HuggingFace cache directories on the SSD:

```bash
mkdir -p /ssd/docker/data /ssd/docker/.cache/huggingface
```

---

## 3. Install NVIDIA Container Toolkit

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

## 4. Model Notes

- Model: `ggml-org/gemma-4-31B-it-GGUF` (multimodal, text + image). Default quant
  `Q4_K_M` (~18.7 GB) fits the Orin's 64 GB comfortably. (Q8_0 ~32.6 GB also fits, but
  only change it if you change it on every platform.)
- llama.cpp version: the `gemma4` architecture requires a recent llama.cpp build (the
  GGUF was produced with llama.cpp release ≈ `b8778`). If the server errors
  `unknown model architecture: 'gemma4'`, the container's llama.cpp is too old. Pull a
  newer `llama_cpp` Jetson image. (The technician hit this exact error running Gemma-4 via
  an older Ollama/llama.cpp build.)
- `llama-server -hf` downloads the GGUF and its vision projector (`mmproj`) into
  `LLAMA_CACHE` (set to `/root/.cache/huggingface` in the image). Mount the SSD cache
  (`-v /ssd/docker/.cache/huggingface:/root/.cache/huggingface`) so the download persists.

Reference for Jetson LLM/VLM containers: https://www.jetson-ai-lab.com/models/

---

## 5. Build the Server Image

From this directory ([`vlm_preintegration/`](.)):

```bash
docker build -f Dockerfile.orin -t opennav-vlm-orin .
```

---

## 6. Run the Server

Launch the model server directly from NVIDIA's prebuilt container (it serves on `:8080`):

```bash
docker run -it --rm --pull always --runtime=nvidia --network host \
  -v /ssd/docker/data:/data \
  -v /ssd/docker/.cache/huggingface:/root/.cache/huggingface \
  ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin \
  llama-server -hf ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
```

The bundled [`Dockerfile.orin`](Dockerfile.orin) bakes this same `llama-server` invocation,
so you can alternatively build it (section 5) and run with the same runtime/cache flags:

```bash
docker run --rm -it --runtime=nvidia --network host \
  -v /ssd/docker/.cache/huggingface:/root/.cache/huggingface \
  opennav-vlm-orin
```

---

## 7. Verify

First call blocks while the model downloads to the NVMe and loads; subsequent calls are
fast.

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

## 8. Connect the Benchmark

[`vlm_params.yaml`](../opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml)
already points at this server:

```yaml
base_url: "http://localhost:8080/v1"
api_key: "EMPTY"
model: "gemma-4"
```

No changes needed when the server runs on the same host. For a remote host, set `base_url`
to `http://<host-ip>:8080/v1`.

---

## Further Reading

- [Jetson AI Lab: LLM/VLM Models & Containers](https://www.jetson-ai-lab.com/models/)
- [NVIDIA SDK Manager: Jetson Flashing](https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
- [Jetson NVMe + Docker Storage Setup](https://www.jetson-ai-lab.com/tutorials/ssd-docker-setup/)
- [ggml-org/gemma-4-31B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF)
