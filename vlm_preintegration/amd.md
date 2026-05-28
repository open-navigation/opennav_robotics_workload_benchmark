# AMD Strix Halo: Gemma-4 31B VLM Setup & Runtime

Serve Gemma-4 31B as an OpenAI-compatible VLM endpoint on the AMD Strix Halo platform using llama.cpp (via the AMD `ryzers` framework on ROCm). The server
listens on `http://localhost:8080/v1`, which the benchmark's [`vlm_params.yaml`](../opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml) already targets out of the box.

> Benchmark note: All three platforms (AMD, Jetson Orin, Jetson Thor) run the
> *identical* model `ggml-org/gemma-4-31B-it-GGUF:Q4_K_M` through `llama-server`.
> Keep the model and quant identical across platforms for a valid 1:1 comparison.

---

## 1. OS & Kernel

After a fresh Ubuntu install, reboot, log in, and update:

```bash
sudo apt-get update && sudo apt-get upgrade
```

Install the OEM kernel and reboot:

```bash
sudo apt update && sudo apt install linux-oem-24.04c
sudo reboot
```

---

## 2. ROCm Drivers & GPU Memory

Install and configure the ROCm drivers for Ryzen following AMD's guide:

- https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/install-ryzen.html

In particular, configure shared memory in BIOS and Linux. The BIOS may call this
"Graphics Buffer Memory" (the docs call it VRAM). AMD recommends setting this to the
lowest possible value (512M-2G depending on BIOS version). The GPU draws the rest
from shared system memory (GTT):

- https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/install-ryzen.html#configure-shared-memory

---

## 3. Docker

Install Docker Engine (https://docs.docker.com/engine/install/ubuntu/):

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
```

---

## 4. Install ryzers & Build llama.cpp

Install git and a Python venv, then install the AMD `ryzers` framework:

```bash
sudo apt-get install vim git
sudo apt install python3-venv python3-pip
python3 -m venv ~/venv
source ~/venv/bin/activate

mkdir -p ~/projects && cd ~/projects
git clone https://github.com/amdresearch/ryzers
cd ryzers/
pip install -e .
```

Build the llama.cpp image with `ryzers`, tagging the final image `llamacpp`:

```bash
ryzers build --name llamacpp llamacpp
```

This builds a two-stage chain (`ryzer_env`, then llama.cpp from the
`rocm/pytorch:rocm7.2.2_ubuntu24.04_py3.12_pytorch_release_2.10.0` base, compiled for the
`gfx1151` Strix Halo iGPU) and tags the final image `llamacpp`. Confirm it:

```bash
docker images | grep llamacpp
```

We use `ryzers build` only to produce this image. Everything below uses plain `docker build`
/ `docker run` (not `ryzers run`), so [`Dockerfile.amd`](Dockerfile.amd) is `FROM llamacpp`.

---

**Stop here if setting up for the benchmark pipeline. Below this is a full-setup for the VLM which may be useful outside of the context of the benchmark. See the pipieline's `README.md` for instructions for building the containers for the benchmark.
**
---

## 5. Build the Server Image

From this directory ([`vlm_preintegration/`](.)):

```bash
docker build -f Dockerfile.amd -t opennav-vlm-amd .
```

> [`Dockerfile.amd`](Dockerfile.amd) is `FROM llamacpp`. If you tagged the `ryzers build`
> image differently (via `--name`), update its `FROM` line to match.

### Model Notes

- Model: `ggml-org/gemma-4-31B-it-GGUF` (multimodal, text + image). Default quant
  `Q4_K_M` (~18.7 GB) fits the EVO-X2's unified memory; do not change it unless you
  also change it on the Jetsons.
- llama.cpp version: the `gemma4` architecture requires a recent llama.cpp build (the
  GGUF was produced with llama.cpp release ≈ `b8778`). If the server errors
  `unknown model architecture: 'gemma4'`, the bundled llama.cpp is too old. Rebuild the
  ryzers image against current `llama.cpp`.
- `llama-server -hf` downloads the GGUF and its vision projector (`mmproj`) into
  `LLAMA_CACHE` (set to `/root/.cache/huggingface` in the image). The run command's
  `-v $PWD/llamacpp_cache:/root/.cache` mount (section 7) persists these across restarts.

---

## 6. Run the Server

Run the image with plain `docker run` (these are the flags `ryzers run` would generate). Its
entrypoint auto-launches `llama-server`, so the server comes up on `:8080`:

```bash
mkdir -p $PWD/llamacpp_cache
docker run --rm -it \
  --shm-size 16G \
  --cap-add=SYS_PTRACE \
  --network=host \
  --ipc=host \
  --device=/dev/kfd \
  --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --group-add video \
  --group-add render \
  -v $PWD/llamacpp_cache:/root/.cache \
  opennav-vlm-amd
```

Notes:
- `-v $PWD/llamacpp_cache:/root/.cache` is the model-persistence mount. It binds the whole
  `/root/.cache`, so the downloaded GGUF shards and the vision `mmproj` (under `LLAMA_CACHE`,
  i.e. `/root/.cache/huggingface`) survive container restarts. This single mount is sufficient;
  no separate model or HuggingFace-cache directory needs mounting.
- If ROCm doesn't detect the `gfx1151` iGPU, add `-e HSA_OVERRIDE_GFX_VERSION=11.5.1`.
- The headless server does not need the extra flags `ryzers run` adds for interactive use:
  X11 (`-e DISPLAY=$DISPLAY`, `-v /tmp/.X11-unix:/tmp/.X11-unix`), one `--device` per
  `/dev/video*`, or the `$PWD/images` / `$PWD/scripts` mounts.
- For the benchmark pipeline, the same image is launched detached via `VLM_IMAGE`; host
  networking already exposes `:8080` to match `vlm_params.yaml`.

---

## 7. Verify

First call blocks while the model downloads/loads; subsequent calls are fast.

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

- [AMD ROCm + Ryzen on Linux](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/howto_native_linux.html)
- [amdresearch/ryzers](https://github.com/amdresearch/ryzers)
- [ggml-org/gemma-4-31B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF)
