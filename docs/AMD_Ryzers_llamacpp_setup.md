# Setup Instructions for Ryzers Environment on AMD NucBox-EVO-X2



After Ubuntu has been installed and you have successfully rebooted and logged in

`sudo apt-get update && sudo apt-get upgrade`

### Install OEM kernel

```
sudo apt update && sudo apt install linux-oem-24.04c
```

Reboot and proceed with the other steps below

### Install and Configure ROCM drivers and GPU Performance. 

Follow the instructions here:
https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/install-ryzen.html

Ensure these steps in particular are done:
Configure Shared Memory in BIOS and Linux.
Note the BIOS may call this "Graphics Buffer Memory", which the documentation refers to VRAM. 
AMD recommends setting this to the lowest possible value(512M-2G will display depending on BIOS version)

https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/install-ryzen.html#configure-shared-memory

### Setup docker

 https://docs.docker.com/engine/install/ubuntu/

### Add Docker's official GPG key:
```
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc


```

### Add the repository to Apt sources:
```
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



### Install git and setup venv
```
sudo apt-get install vim git
sudo apt install python3-venv python3-pip
python3 -m venv ~/venv
source ~/venv/bin/activate
```

### Install ryzers
```
mkdir projects
cd projects/
git clone https://github.com/amdresearch/ryzers
cd ryzers/
pip install -e . 
```

### Build llamacpp docker and run Gemma4

```
cd Ryzers
ryzers build llamacpp
ryzers run bash
export PATH=/ryzers/llamacpp/build/bin:$PATH
```

### Confirm llamacpp install and ryzers environment config:

`llama-cli -hf ggml-org/gemma-4-E2B-it-GGUF --prompt "Write a poem about the Kraken."`

### Working within the ryzers environment.

The `ryzers` command is actually a wrapper script for starting a Docker container inside the Python `venv`. 
Users needing to interact with the llama-server config or ryzers environment will execute these steps each time post-install:

```
source ~/venv/bin/activate
cd Ryzers
ryzers run bash
export PATH=/ryzers/llamacpp/build/bin:$PATH
```

The `run_ryzers_docker.sh` is a single-line BASH script that launches a Docker container using standard Docker syntax. Users can add additional mounts, network privileges, and other standard docker runtime parameters if needed. For example, if you wanted to have local storage for an image cache for llama-server to access for visual prompting. 

### Further Reading:

[AMD Guide for ROCM & Ryzen on Linux](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/howto_native_linux.html) 

