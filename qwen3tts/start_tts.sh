#!/bin/bash
# start_tts.sh — 啟動 Qwen3-TTS API Server (port 8003)
# 前置：bash qwen3_tts.sh（安裝依賴並下載模型）
#
# 環境變數：
#   TTS_MODEL   模型名稱（預設 Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice）
#   TTS_MODE    模式：custom（內建音色）或 base（語音複製）
#   TTS_PORT    Port（預設 8003）
#
# 模型選項：
#   custom 模式（預設）：
#     Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice   (推薦 ✅)
#     Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
#     Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
#   base 模式（語音複製）：
#     Qwen/Qwen3-TTS-12Hz-1.7B-Base
#     Qwen/Qwen3-TTS-12Hz-0.6B-Base
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

TTS_MODEL="${TTS_MODEL:-Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice}"
TTS_MODE="${TTS_MODE:-custom}"
TTS_PORT="${TTS_PORT:-8003}"

echo "=== 啟動 Qwen3-TTS API Server ==="
echo "模型：$TTS_MODEL"
echo "模式：$TTS_MODE"
echo "位址：http://0.0.0.0:$TTS_PORT"
echo ""

../.venv/bin/python3 -c "import qwen_tts" 2>/dev/null || {
    echo "❌ qwen-tts 未安裝，請先執行：bash tts/qwen3_tts.sh"
    exit 1
}

export TTS_MODEL TTS_MODE
../.venv/bin/python3 tts_api.py "$TTS_PORT"
