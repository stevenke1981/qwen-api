#!/bin/bash
# asr_benchmark.sh — Qwen3-ASR 性能測試
set -e

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")"

VENV="../.venv/bin/python3"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-ASR 性能基準測試                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "測試選項："
echo "  1) 1.7B 模型（推薦）"
echo "  2) 0.6B 模型（輕量）"
echo "  3) 0.6B vs 1.7B 對比"
echo "  4) 1.7B + 時間戳記"
echo ""
read -rp "請選擇 [1-4]（預設 1）：" CHOICE
CHOICE="${CHOICE:-1}"

case "$CHOICE" in
  1) ARGS="--model 1.7b" ;;
  2) ARGS="--model 0.6b" ;;
  3) ARGS="--model both" ;;
  4) ARGS="--model 1.7b --timestamps" ;;
  *) ARGS="--model 1.7b" ;;
esac

echo ""
echo "開始測試..."
echo ""
$VENV asr_benchmark.py $ARGS
