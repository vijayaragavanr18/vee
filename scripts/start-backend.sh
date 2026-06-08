#!/bin/bash
set -e
echo "=== VeeTrack startup ==="

# 1. Start vLLM inference server
if ! pgrep -f "vllm.entrypoints.openai.api_server" > /dev/null; then
    echo "[1/3] Starting vLLM (Qwen2.5-3B-AWQ)..."
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen2.5-3B-Instruct-AWQ \
        --quantization awq \
        --enable-prefix-caching \
        --port 8000 \
        --max-model-len 4096 \
        > /tmp/vllm.log 2>&1 &
    
    echo "Waiting for vLLM to initialize (this may take a minute)..."
    while ! curl -s http://localhost:8000/v1/models > /dev/null; do
        sleep 5
    done
fi

# 2. Pre-warm model into VRAM
echo "[2/3] Warming up vLLM..."
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen2.5-3B-Instruct-AWQ","messages":[{"role":"user","content":"ready"}],"max_tokens":10}' > /dev/null
echo "LLM warm."

# 3. Start FastAPI
echo "[3/3] Starting FastAPI..."
# Note: Since vLLM runs on 8000, we run FastAPI on 8001
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1

echo "=== VeeTrack ready at http://localhost:8001 ==="
