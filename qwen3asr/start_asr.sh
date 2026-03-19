#!/bin/bash
# start_asr.sh — 啟動 Qwen3-ASR API Server (port 8002)
# 前置：bash qwen3_asr.sh（安裝依賴並下載模型）
#
# 環境變數：
#   ASR_MODEL       模型名稱（預設 Qwen/Qwen3-ASR-1.7B）
#   ASR_TIMESTAMPS  啟用時間戳記（預設 false）
#   ASR_PORT        Port（預設 8002）
#   API_KEY         單一 API Key（空字串 = 不驗證）
#   API_KEYS        多個 API Key，逗號分隔（優先於 API_KEY）
#
# 使用範例：
#   bash start_asr.sh                              # 無驗證（本機開發）
#   API_KEY=sk-xxx bash start_asr.sh               # 單 Key
#   API_KEYS=sk-a,sk-b,sk-c bash start_asr.sh      # 多 Key
#   ASR_MODEL=Qwen/Qwen3-ASR-0.6B ASR_TIMESTAMPS=true \
#     API_KEY=sk-xxx bash start_asr.sh             # 完整設定
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

ASR_MODEL="${ASR_MODEL:-Qwen/Qwen3-ASR-1.7B}"
ASR_PORT="${ASR_PORT:-8002}"
API_KEY="${API_KEY:-}"
API_KEYS="${API_KEYS:-}"

# 計算認證模式顯示文字
if [ -n "$API_KEYS" ]; then
    KEY_COUNT=$(echo "$API_KEYS" | tr ',' '\n' | grep -c .)
    AUTH_MODE="多 Key（$KEY_COUNT 組）"
elif [ -n "$API_KEY" ]; then
    AUTH_MODE="單 Key"
else
    AUTH_MODE="停用（無驗證，僅限本機）"
fi

echo "=== 啟動 Qwen3-ASR API Server ==="
echo "模型：$ASR_MODEL"
echo "位址：http://0.0.0.0:$ASR_PORT"
echo "時間戳記：${ASR_TIMESTAMPS:-false}"
echo "認證模式：$AUTH_MODE"
echo ""
echo "端點："
echo "  GET  /health                       健康檢查（不需驗證）"
echo "  POST /transcribe                   上傳音訊辨識"
echo "  POST /transcribe/url               URL 音訊辨識"
echo "  POST /v1/audio/transcriptions      OpenAI Whisper 相容格式"
echo ""

../.venv/bin/python3 -c "import qwen_asr" 2>/dev/null || {
    echo "❌ qwen-asr 未安裝，請先執行：bash qwen3asr/qwen3_asr.sh"
    exit 1
}

export ASR_MODEL ASR_TIMESTAMPS API_KEY API_KEYS
../.venv/bin/python3 asr_api.py "$ASR_PORT"
