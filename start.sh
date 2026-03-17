#!/bin/bash
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

# 載入設定
set -a; source .env; set +a

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MODEL_PATH="${MODEL_PATH:-$HOME/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf}"
N_GPU_LAYERS="${N_GPU_LAYERS:--1}"
N_CTX="${N_CTX:-8192}"
N_BATCH="${N_BATCH:-512}"

echo "=== 啟動 Qwen3.5-9B API ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "文件：http://localhost:$PORT/docs"
echo ""

exec llama-server \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --n-gpu-layers "$N_GPU_LAYERS" \
    --ctx-size "$N_CTX" \
    --batch-size "$N_BATCH" \
    --chat-template chatml
