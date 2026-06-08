#!/bin/bash
set -e
echo "=== Starting vLLM (Enterprise Mode) ==="

# vLLM configured for 24GB VRAM target.
# - 75% GPU utilization (~18GB including KV cache)
# - FP8 KV Cache to save memory for long contexts
# - AWQ 4-bit quantization for high throughput

if ! pgrep -f "vllm.entrypoints.openai.api_server" > /dev/null; then
    echo "Launching vLLM (Qwen2.5-3B-AWQ)..."
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen2.5-3B-Instruct-AWQ \
        --quantization awq \
        --enable-prefix-caching \
        --gpu-memory-utilization 0.75 \
        --kv-cache-dtype fp8 \
        --port 8000 \
        --max-model-len 4096 \
        --guided-decoding-backend outlines \
        > /tmp/vllm.log 2>&1 &
    
    echo "Waiting for vLLM to initialize..."
    while ! curl -s http://localhost:8000/v1/models > /dev/null; do
        sleep 5
    done
    echo "vLLM successfully initialized on port 8000."
else
    echo "vLLM is already running."
fi
