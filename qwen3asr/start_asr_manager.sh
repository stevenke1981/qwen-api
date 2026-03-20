#!/bin/bash
# start_asr_manager.sh — 啟動 Qwen3-ASR 多模型管理器
#
# 環境變數：
#   ASR_DEFAULT_MODEL   啟動時預載模型 ID（預設 asr-1.7b）
#   ASR_TIMESTAMPS      啟用時間戳記 true/false（預設 false）
#   ASR_MGR_PORT        Port（預設 8002）
#   API_KEY             單一 API Key
#   API_KEYS            多 API Key（逗號分隔）
#
# 模型 ID 對照：
#   asr-0.6b   Qwen/Qwen3-ASR-0.6B  （輕量快速）
#   asr-1.7b   Qwen/Qwen3-ASR-1.7B  （高精度 ← 預設）
#
# 用法：
#   bash start_asr_manager.sh
#   ASR_DEFAULT_MODEL=asr-0.6b bash start_asr_manager.sh
#   ASR_TIMESTAMPS=true API_KEY=sk-xxx bash start_asr_manager.sh
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

ASR_DEFAULT_MODEL="${ASR_DEFAULT_MODEL:-asr-1.7b}"
ASR_TIMESTAMPS="${ASR_TIMESTAMPS:-false}"
ASR_MGR_PORT="${ASR_MGR_PORT:-8002}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-ASR 多模型管理器                                 ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  管理 UI     → http://0.0.0.0:$ASR_MGR_PORT/"
echo "  API         → http://0.0.0.0:$ASR_MGR_PORT/v1/audio/transcriptions"
echo "  預載模型    → $ASR_DEFAULT_MODEL"
echo "  時間戳記    → $ASR_TIMESTAMPS"
echo ""

../.venv/bin/python3 -c "import qwen_asr" 2>/dev/null || {
    echo "❌ qwen-asr 未安裝，請先執行：bash qwen3_asr.sh"
    exit 1
}

export ASR_DEFAULT_MODEL ASR_TIMESTAMPS
../.venv/bin/python3 asr_manager.py "$ASR_MGR_PORT"
