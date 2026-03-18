#!/bin/bash
# start_asr.sh — 啟動 Qwen3-ASR API Server (port 8002)
# 前置：bash qwen3_asr.sh（安裝依賴並下載模型）
#
# 環境變數：
#   ASR_MODEL       模型名稱（預設 Qwen/Qwen3-ASR-1.7B）
#   ASR_TIMESTAMPS  啟用時間戳記（預設 false）
#   ASR_PORT        Port（預設 8002）
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

ASR_MODEL="${ASR_MODEL:-Qwen/Qwen3-ASR-1.7B}"
ASR_PORT="${ASR_PORT:-8002}"

echo "=== 啟動 Qwen3-ASR API Server ==="
echo "模型：$ASR_MODEL"
echo "位址：http://0.0.0.0:$ASR_PORT"
echo "時間戳記：${ASR_TIMESTAMPS:-false}"
echo ""

../.venv/bin/python3 -c "import qwen_asr" 2>/dev/null || {
    echo "❌ qwen-asr 未安裝，請先執行：bash asr/qwen3_asr.sh"
    exit 1
}

export ASR_MODEL ASR_TIMESTAMPS
../.venv/bin/python3 asr_api.py "$ASR_PORT"
