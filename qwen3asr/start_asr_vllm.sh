#!/bin/bash
# start_asr_vllm.sh — 啟動 Qwen3-ASR API Server（vLLM 高效能後端，port 8002）
# 前置：bash asr/qwen3_asr.sh（安裝基礎依賴並下載模型）
#
# vLLM vs Transformers 比較：
#   Transformers：簡單、穩定，適合低並發
#   vLLM：        高吞吐、支援批次 128 並發，適合生產環境
#
# 環境變數：
#   ASR_MODEL      模型名稱（預設 Qwen/Qwen3-ASR-1.7B）
#   ASR_TIMESTAMPS 啟用時間戳記（預設 false）
#   ASR_GPU_UTIL   GPU 使用率（預設 0.7，即 70%）
#   ASR_PORT       Port（預設 8002）
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

ASR_MODEL="${ASR_MODEL:-Qwen/Qwen3-ASR-1.7B}"
ASR_PORT="${ASR_PORT:-8002}"
ASR_GPU_UTIL="${ASR_GPU_UTIL:-0.7}"

echo "=== 啟動 Qwen3-ASR API Server [vLLM 後端] ==="
echo "模型：$ASR_MODEL"
echo "位址：http://0.0.0.0:$ASR_PORT"
echo "時間戳記：${ASR_TIMESTAMPS:-false}"
echo "GPU 使用率：$ASR_GPU_UTIL"
echo ""

# 確認 vLLM 已安裝
../.venv/bin/python3 -c "import vllm" 2>/dev/null || {
    echo "  安裝 qwen-asr[vllm]..."
    uv pip install "qwen-asr[vllm]" --quiet
}

export ASR_MODEL ASR_TIMESTAMPS ASR_GPU_UTIL
../.venv/bin/python3 asr_api_vllm.py "$ASR_PORT"
