# Setup Instructions for llama.cpp on NVIDIA Jetson Thor 5000

---

### Flash JetPack via NVIDIA SDK Manager

Install JetPack OS on the Thor using the USB Debug/Flashing port and NVIDIA SDK Manager on a host Ubuntu machine.

Follow the full flashing guide here:
https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation

- Connect the Jetson to your host machine via the USB Debug/Flashing port
- In SDK Manager, select the Jetson Thor as your target hardware
- Select the appropriate JetPack version and include CUDA, cuDNN, and TensorRT components
- Complete the flashing and component installation steps

After flashing, boot the Jetson and complete initial OS setup, then:

```
sudo apt-get update && sudo apt-get upgrade
```

---

### Install NVIDIA Container Toolkit

```
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Full documentation:
https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html

Verify GPU access from within a container:

```
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

---

### Install git and setup venv

```
sudo apt-get install vim git
sudo apt install python3-venv python3-pip
python3 -m venv ~/venv
source ~/venv/bin/activate
```

---

### Pull and Run llama.cpp Container

NVIDIA maintains pre-built llama.cpp containers for Jetson via the Jetson AI Lab.

Reference for available models and container tags:
https://www.jetson-ai-lab.com/models/

Pull the llama.cpp container:

```
docker pull ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin
```

Run the container with GPU access and local model storage mounted:

```
docker run --rm -it \
  --runtime=nvidia \
  --gpus all \
  -v ~/models:/models \
  ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin \
  bash
```

---

### Confirm llama.cpp Install

Inside the container, confirm the install and run a test inference:
*Note: the `gemma-4-E2B-it-GGUF ` model is used here to provide a quick-loading/quick-turnaround example(it's also expected that most users will actually run llama-server with a model of their choice)*

```
export PATH=/usr/local/bin:$PATH
llama-cli -hf ggml-org/gemma-4-E2B-it-GGUF --prompt "Write a poem about the Kraken."
```

---

### Working Within the Container Environment

Each session, reactivate the venv and re-enter the container:

```
source ~/venv/bin/activate
docker run --rm -it \
  --runtime=nvidia \
  --gpus all \
  -v ~/models:/models \
  ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin \
  bash
```

The `-v ~/models:/models` mount makes your local model cache available inside the container. Additional mounts, network flags, and other standard Docker runtime parameters can be appended as needed.

---

### Further Reading

- [Jetson AI Lab — LLM Models & Containers](https://www.jetson-ai-lab.com/models/)
- [NVIDIA SDK Manager — Jetson Flashing](https://docs.nvidia.com/sdk-manager/install-with-sdkm-jetson/index.html#step-03-installation)
- [NVIDIA Container Toolkit Documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html)
