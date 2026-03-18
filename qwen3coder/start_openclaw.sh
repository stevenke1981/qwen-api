#!/bin/bash
# start_openclaw.sh — llama-server 專為 OpenClaw / Claude Code 風格 agent 優化
# 模型：Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M（OpenClaw 指定）
# 差異：
#   - 使用 Uncensored 模型，對 coding agent 指令更服從
#   - ctx-size 65536（64k，OpenClaw agent 長對話足夠，VRAM ~9.5 GB）
#   - n-predict 2048（agent 回應不需超長，加快速度）
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
N_CTX=65536       # 64k context，OpenClaw agent 長對話足夠，VRAM 有餘裕
N_BATCH=1024
N_UBATCH=512
CACHE_TYPE_K="${CACHE_TYPE_K:-q8_0}"
CACHE_TYPE_V="${CACHE_TYPE_V:-q8_0}"

echo "=== 啟動 llama-server for OpenClaw ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "Context：$N_CTX  max predict：2048  (VRAM ~10-11 GB)"
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
