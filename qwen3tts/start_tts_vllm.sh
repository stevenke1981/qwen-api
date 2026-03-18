#!/bin/bash
# start_tts_vllm.sh — 啟動 Qwen3-TTS API Server（vLLM 加速後端，port 8003）
# 前置：bash tts/qwen3_tts.sh（安裝基礎依賴並下載模型）
#
# vLLM 版本新增功能：
#   - /synthesize/batch  批次合成多筆，回傳 ZIP（相較單筆效率提升）
#   - torch.compile 加速（若 vLLM 可用）
#   - 自動退回 transformers 後端（相容模式）
#
# 注意：Qwen3-TTS 使用離散音訊 token，vLLM 原生不支援音訊解碼。
#       本版本使用 torch.compile 優化 + 批次推理作為加速策略。
#
# 環境變數：
#   TTS_MODEL    模型名稱（預設 Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice）
#   TTS_MODE     模式：custom 或 base（預設 custom）
#   TTS_GPU_UTIL GPU 使用率（預設 0.7）
#   TTS_PORT     Port（預設 8003）
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

TTS_MODEL="${TTS_MODEL:-Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice}"
TTS_MODE="${TTS_MODE:-custom}"
TTS_PORT="${TTS_PORT:-8003}"
TTS_GPU_UTIL="${TTS_GPU_UTIL:-0.7}"

echo "=== 啟動 Qwen3-TTS API Server [vLLM 加速後端] ==="
echo "模型：$TTS_MODEL"
echo "模式：$TTS_MODE"
echo "位址：http://0.0.0.0:$TTS_PORT"
echo "GPU 使用率：$TTS_GPU_UTIL"
echo ""

../.venv/bin/python3 -c "import qwen_tts" 2>/dev/null || {
    echo "❌ qwen-tts 未安裝，請先執行：bash tts/qwen3_tts.sh"
    exit 1
}

# 嘗試安裝 vllm（可選）
../.venv/bin/python3 -c "import vllm" 2>/dev/null || {
    echo "  vLLM 未安裝，嘗試安裝..."
    uv pip install vllm --quiet 2>/dev/null || echo "  ⚠ vLLM 安裝失敗，將使用 torch.compile 加速"
}

export TTS_MODEL TTS_MODE TTS_GPU_UTIL
../.venv/bin/python3 tts_api_vllm.py "$TTS_PORT"
