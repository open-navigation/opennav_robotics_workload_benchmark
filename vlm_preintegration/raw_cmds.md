Models running via llama-cpp as of 5/28:
Orin:ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
Thor:ggml-org/gemma-4-31B-it-GGUF:Q4_K_M
AMD:ggml-org/gemma-4-31B-it-GGUF:Q4_K_M

Orin Launch:
docker run -it --rm --pull always --runtime=nvidia --network host  -v /ssd/docker/data:/data -v /ssd/docker/.cache/huggingface:/root/.cache/huggingface ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-orin llama-server -hf ggml-org/gemma-4-31B-it-GGUF:Q4_K_M

Thor Launch:
docker run -it --rm --pull always --runtime=nvidia --network host -v $HOME/.cache/huggingface:/root/.cache/huggingface ghcr.io/nvidia-ai-iot/llama_cpp:latest-jetson-thor llama-server -hf ggml-org/gemma-4-31B-it-GGUF:Q4_K_M

AMD Launch:

docker run -it --rm --shm-size 16G --cap-add=SYS_PTRACE  --network=host --ipc=host -v $PWD/images:/images -v $PWD/scripts:/scri
pts -v $PWD/llamacpp_cache:/root/.cache --device=/dev/kfd --device=/dev/dri --security-opt seccomp=unconfined --group-add video
 --group-add render  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix  ryzerdocker $1
 
llama-server -hf ggml-org/gemma-4-31B-it-GGUF 
