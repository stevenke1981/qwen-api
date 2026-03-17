#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"
source .venv/bin/activate

MODEL_REPO="bartowski/Qwen_Qwen3.5-9B-GGUF"
MODEL_FILE="Qwen_Qwen3.5-9B-Q5_K_M.gguf"
MODEL_DIR="$HOME/models"
MODEL_PATH="$MODEL_DIR/$MODEL_FILE"

echo "=== 下載模型 ==="
echo "來源：$MODEL_REPO"
echo "檔案：$MODEL_FILE（6.86 GB）"
echo "路徑：$MODEL_PATH"
echo ""

mkdir -p "$MODEL_DIR"

# 加速下載
export HF_HUB_ENABLE_HF_TRANSFER=1

python3 - <<EOF
from huggingface_hub import hf_hub_download
import os

print("開始下載，請稍候...")
path = hf_hub_download(
    repo_id="$MODEL_REPO",
    filename="$MODEL_FILE",
    local_dir="$MODEL_DIR",
)
print(f"\n模型已儲存至：{path}")
EOF

echo ""
echo "=== 下載完成 ==="
echo "啟動 API：bash start.sh"
