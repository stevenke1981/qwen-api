#!/bin/bash
# start_openclaw.sh — llama-server 專為 OpenClaw / Claude Code 風格 agent 優化
# 差異：
#   - 使用 Qwen2.5-Coder 模型（coding 優化）
#   - ctx-size 16384（coding 用不到 32k，省 VRAM）
#   - n-predict 2048（agent 回應不需超長，加快速度）
#   - 關閉 fetch proxy（OpenClaw 有自己的 tools）
#   - port 8000（與 start.sh 相同，不衝突）
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

# 載入基礎設定（可被下方覆寫）
[ -f .env ] && { set -a; source .env; set +a; }

# OpenClaw 專用參數（覆寫 .env）
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
MODEL_PATH="${CODER_MODEL_PATH:-$HOME/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf}"
N_GPU_LAYERS="${N_GPU_LAYERS:--1}"
N_CTX=16384       # 夠用且省 VRAM
N_BATCH=1024
N_UBATCH=512
CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}"

# 若 Coder 模型不存在，退回預設模型
if [ ! -f "$MODEL_PATH" ]; then
    echo "⚠  找不到 Coder 模型：$MODEL_PATH"
    MODEL_PATH="${MODEL_PATH:-$HOME/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf}"
    echo "   退回使用：$MODEL_PATH"
    echo "   建議先執行：bash 05_download_model.sh（選 3）"
    echo ""
fi

echo "=== 啟動 llama-server for OpenClaw ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "Context：$N_CTX  max predict：2048"
echo ""

llama-server \
    --model         "$MODEL_PATH" \
    --host          "$HOST" \
    --port          "$PORT" \
    --n-gpu-layers  "$N_GPU_LAYERS" \
    --ctx-size      "$N_CTX" \
    --batch-size    "$N_BATCH" \
    --ubatch-size   "$N_UBATCH" \
    --cache-type-k  "$CACHE_TYPE_K" \
    --cache-type-v  "$CACHE_TYPE_V" \
    --flash-attn    on \
    --n-predict     2048 \
    --jinja
