#!/bin/bash
# start_openclaw_fast.sh — OpenClaw 極速模式
# 模型：Qwen3.5-9B Q3_K_M（比 Q4_K_M 快 ~25%，品質略降）
# 差異（相較 start_openclaw_nothink.sh）：
#   - 使用 Q3_K_M 量化（更小更快）
#   - thinking 模式關閉
#   - KV cache q4_0（VRAM 最省）
#   - ctx-size 65536
#   - VRAM ~6.5 GB（最寬裕）
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

[ -f .env ] && { set -a; source .env; set +a; }

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MODEL_PATH="${OPENCLAW_FAST_MODEL_PATH:-$HOME/models/Qwen_Qwen3.5-9B-Q3_K_M.gguf}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "⚠  找不到模型：$MODEL_PATH"
    echo "   請先下載 Q3_K_M 量化版："
    echo "   bash download_qwen35.sh（選 Qwen3.5-9B，量化選 Q3_K_M）"
    exit 1
fi

N_GPU_LAYERS="${N_GPU_LAYERS:--1}"
N_CTX=65536
N_BATCH=1024
N_UBATCH=512

echo "=== 啟動 llama-server for OpenClaw [極速模式] ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "Context：$N_CTX  KV cache：q4_0  thinking：OFF  (VRAM ~6.5 GB)"
echo ""

llama-server \
    --model         "$MODEL_PATH" \
    --host          "$HOST" \
    --port          "$PORT" \
    --n-gpu-layers  "$N_GPU_LAYERS" \
    --ctx-size      "$N_CTX" \
    --batch-size    "$N_BATCH" \
    --ubatch-size   "$N_UBATCH" \
    --cache-type-k  q4_0 \
    --cache-type-v  q4_0 \
    --flash-attn    on \
    --n-predict     2048 \
    --jinja \
    --reasoning     off
