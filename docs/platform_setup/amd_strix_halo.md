# AMD Strix Halo: Gemma-4 31B VLM Setup & Runtime

Serve Gemma-4 31B as an OpenAI-compatible VLM endpoint on the AMD Strix Halo platform using llama.cpp (via the AMD `ryzers` framework on ROCm). The server
listens on `http://localhost:8080/v1`, which the benchmark's [`vlm_params.yaml`](../../opennav_benchmark_ai_workload/opennav_benchmark_vlm/config/vlm_params.yaml) already targets out of the box.

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
/ `docker run` (not `ryzers run`).

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

## Further Reading

- [AMD ROCm + Ryzen on Linux](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/howto_native_linux.html)
- [amdresearch/ryzers](https://github.com/amdresearch/ryzers)
- [ggml-org/gemma-4-31B-it-GGUF](https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF)
