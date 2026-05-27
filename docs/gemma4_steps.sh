## Just installed ubuntu, fresh boot
#sudo apt-get update && sudo apt-get upgrade
#
## Setup docker copy-paste from https://docs.docker.com/engine/install/ubuntu/
#########################################################
## Add Docker's official GPG key:
#sudo apt update
#sudo apt install ca-certificates curl
#sudo install -m 0755 -d /etc/apt/keyrings
#sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
#sudo chmod a+r /etc/apt/keyrings/docker.asc
#
## Add the repository to Apt sources:
#sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
#Types: deb
#URIs: https://download.docker.com/linux/ubuntu
#Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
#Components: stable
#Signed-By: /etc/apt/keyrings/docker.asc
#EOF

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
########################################################

# Install git and setup venv
sudo apt-get install vim git
sudo apt install python3-venv python3-pip
python3 -m venv ~/venv
source ~/venv/bin/activate

# Install ryzers
mkdir projects
cd projects/
git clone https://github.com/amdresearch/ryzers
cd ryzers/
pip install -e .

# Install OEM kernel
sudo apt update && sudo apt install linux-oem-24.04cOnce ryzers setup build and run the llamacpp package

# Build llamacpp docker and run Gemma4
cd Ryzers
ryzers build llamacpp
ryzers run bash
export PATH=/ryzers/llamacpp/build/bin:$PATH
llama-cli -hf ggml-org/gemma-4-E2B-it-GGUF --prompt "Write a poem about the Kraken."
