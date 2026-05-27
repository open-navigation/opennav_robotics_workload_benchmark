# Run llama-cli via venv 
source ~/venv/bin/activate
cd ~/projects/ryzers/
ryzers run bash 
export PATH=/ryzers/llamacpp/build/bin:$PATH
#llama-cli -hf ggml-org/gemma-4-E2B-it-GGUF --prompt "hello"

