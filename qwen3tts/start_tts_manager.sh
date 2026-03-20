#!/bin/bash
# start_tts_manager.sh — 啟動 Qwen3-TTS 多模型管理器
#
# 環境變數：
#   TTS_DEFAULT_MODEL   啟動時預載模型 ID（預設 tts-1.7b-custom）
#   TTS_MGR_PORT        Port（預設 8090）
#
# 模型 ID 對照：
#   tts-0.6b-base       Qwen3-TTS-12Hz-0.6B-Base
#   tts-1.7b-base       Qwen3-TTS-12Hz-1.7B-Base
#   tts-0.6b-custom     Qwen3-TTS-12Hz-0.6B-CustomVoice
#   tts-1.7b-custom     Qwen3-TTS-12Hz-1.7B-CustomVoice  ← 預設
#   tts-1.7b-design     Qwen3-TTS-12Hz-1.7B-VoiceDesign
#
# 用法：
#   bash start_tts_manager.sh
#   TTS_DEFAULT_MODEL=tts-0.6b-custom bash start_tts_manager.sh
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

TTS_DEFAULT_MODEL="${TTS_DEFAULT_MODEL:-tts-1.7b-custom}"
TTS_MGR_PORT="${TTS_MGR_PORT:-8090}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-TTS 多模型管理器                                 ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  管理 UI  → http://0.0.0.0:$TTS_MGR_PORT/"
echo "  API      → http://0.0.0.0:$TTS_MGR_PORT/synthesize"
echo "  預載模型 → $TTS_DEFAULT_MODEL"
echo ""

../.venv/bin/python3 -c "import qwen_tts" 2>/dev/null || {
    echo "❌ qwen-tts 未安裝，請先執行：bash qwen3_tts.sh"
    exit 1
}

export TTS_DEFAULT_MODEL
../.venv/bin/python3 tts_manager.py "$TTS_MGR_PORT"
