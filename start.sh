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
N_CTX="${N_CTX:-32768}"
N_BATCH="${N_BATCH:-1024}"
N_UBATCH="${N_UBATCH:-512}"
CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}"

echo "=== 啟動 Qwen3.5-9B API ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "文件：http://localhost:$PORT/docs"
echo "Context：$N_CTX  KV cache：$CACHE_TYPE_K/$CACHE_TYPE_V"
echo ""

exec llama-server \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --n-gpu-layers "$N_GPU_LAYERS" \
    --ctx-size "$N_CTX" \
    --batch-size "$N_BATCH" \
    --ubatch-size "$N_UBATCH" \
    --cache-type-k "$CACHE_TYPE_K" \
    --cache-type-v "$CACHE_TYPE_V" \
    --defrag-thold 0.1 \
    --flash-attn \
    --chat-template chatml
