#!/bin/bash
# start_llm_manager.sh — 啟動 Qwen LLM 多模型管理器
#
# 環境變數：
#   LLM_DEFAULT_MODEL   啟動時預載模型 ID（預設 chat）
#   LLM_MGR_PORT        Port（預設 8000）
#   LLAMA_PORT          llama-server 內部 Port（預設 8010）
#   MODEL_DIR           GGUF 模型目錄（預設 ~/models）
#   API_KEY             單一 API Key
#   API_KEYS            多 API Key（逗號分隔）
#
# 模型 ID 對照：
#   chat           Qwen3.5-4B Q5_K_M       — 通用對話（預設，低 VRAM）
#   chat-9b        Qwen3.5-9B Q5_K_M       — 通用對話 9B
#   coder-7b       Qwen2.5-Coder-7B Q8_0  — coding 優化
#   coder-14b      Qwen2.5-Coder-14B Q4   — coding 高品質
#   coder-14b-q8   Qwen2.5-Coder-14B Q8   — coding 最高（需 16 GB）
#   openclaw       Qwen3.5-9B Uncensored  — 進階推理
#   openclaw-fast  Qwen3.5-9B Uncensored  — 快速模式（ctx 16k）
#
# 用法：
#   bash start_llm_manager.sh
#   LLM_DEFAULT_MODEL=coder-7b bash start_llm_manager.sh
#   MODEL_DIR=/data/models API_KEY=sk-xxx bash start_llm_manager.sh
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

LLM_DEFAULT_MODEL="${LLM_DEFAULT_MODEL:-chat}"
LLM_MGR_PORT="${LLM_MGR_PORT:-8000}"
LLAMA_PORT="${LLAMA_PORT:-8010}"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen LLM 多模型管理器                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  管理 UI     → http://0.0.0.0:$LLM_MGR_PORT/"
echo "  API         → http://0.0.0.0:$LLM_MGR_PORT/v1/chat/completions"
echo "  預載模型    → $LLM_DEFAULT_MODEL"
echo "  模型目錄    → $MODEL_DIR"
echo "  llama-server 內部 Port → $LLAMA_PORT"
echo ""

# 確認 llama-server 存在
LLAMA_BIN="${LLAMA_BIN:-$(which llama-server 2>/dev/null || echo '')}"
if [ -z "$LLAMA_BIN" ]; then
    # 嘗試常見路徑
    for candidate in \
        "$HOME/llama.cpp/build/bin/llama-server" \
        "$HOME/llama.cpp/llama-server" \
        "/usr/local/bin/llama-server"; do
        if [ -x "$candidate" ]; then
            LLAMA_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$LLAMA_BIN" ]; then
    echo "❌ llama-server 未找到"
    echo "   請先執行 bash 04b_build_llama_cpp.sh 編譯，或設定 LLAMA_BIN 環境變數"
    exit 1
fi

echo "  llama-server → $LLAMA_BIN"
echo ""

export LLM_DEFAULT_MODEL LLAMA_PORT MODEL_DIR LLAMA_BIN
.venv/bin/python3 llm_manager.py "$LLM_MGR_PORT"
