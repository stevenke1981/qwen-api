#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate

source .env

echo "=== 啟動 Qwen3.5-9B API ==="
echo "模型：$MODEL_PATH"
echo "位址：http://$HOST:$PORT"
echo "文件：http://localhost:$PORT/docs"
echo ""

python main.py
