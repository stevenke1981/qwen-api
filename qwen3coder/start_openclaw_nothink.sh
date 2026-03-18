#!/bin/bash
# start_openclaw_nothink.sh — OpenClaw 高速模式
# 模型：Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M（OpenClaw 指定）
# 差異（相較 start_openclaw.sh）：
#   - thinking 模式關閉（省去大量 <think> token，速度顯著提升）
#   - KV cache q4_0（從 q8_0 降低，VRAM -1.75 GB，attention 更快）
#   - ctx-size 65536（64k，VRAM ~7.75 GB，比標準版更有餘裕）
#   - n-predict 2048（agent 回應不需超長）
#   - 不啟動 fetch proxy（OpenClaw 有自己的 tools）
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

# 載入基礎設定（可被下方覆寫）
[ -f ../.env ] && { set -a; source ../.env; set +a; }

# OpenClaw 專用模型（可用 OPENCLAW_MODEL_PATH 環境變數覆寫）
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
OPENCLAW_MODEL="Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
MODEL_PATH="${OPENCLAW_MODEL_PATH:-$HOME/models/$OPENCLAW_MODEL}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "⚠  找不到 OpenClaw 模型：$MODEL_PATH"
    echo "   請先執行：bash 05_download_model.sh（選 5）"
    echo ""
    # 退回 .env 的模型
    [ -f ../.env ] && { set -a; source ../.env; set +a; }
    MODEL_PATH="${MODEL_PATH:-$HOME/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf}"
    echo "   退回使用：$MODEL_PATH"
    echo ""
fi

N_GPU_LAYERS="${N_GPU_LAYERS:--1}"
N_CTX=65536       # 64k context，KV q4_0 下 VRAM ~7.75 GB
N_BATCH=1024
N_UBATCH=512
CACHE_TYPE_K="q4_0"   # q8_0 → q4_0：KV cache VRAM 減半，attention 更快
CACHE_TYPE_V="q4_0"

echo "=== 啟動 llama-server for OpenClaw [NoThink 高速模式] ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "Context：$N_CTX  KV cache：q4_0  thinking：OFF  (VRAM ~7.75 GB)"
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
    --jinja \
    --reasoning     off
