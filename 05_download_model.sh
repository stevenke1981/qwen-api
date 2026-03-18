#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"

# 確保 huggingface_hub 可用
source .venv/bin/activate 2>/dev/null || true

MODEL_DIR="$HOME/models"
mkdir -p "$MODEL_DIR"
export HF_HUB_ENABLE_HF_TRANSFER=1

# ── 可用模型清單 ───────────────────────────────────────────────────────────────
echo "=== 選擇要下載的模型 ==="
echo ""
echo "  1) Qwen3.5-9B Q5_K_M       — 6.86 GB  通用對話（目前預設）"
echo "  2) Qwen2.5-Coder-7B Q8_0   — 8.10 GB  coding 優化，速度快"
echo "  3) Qwen2.5-Coder-14B Q4_K_M — 8.99 GB  coding 優化，品質佳（推薦 OpenClaw）"
echo "  4) Qwen2.5-Coder-14B Q8_0  — 15.7 GB  coding 最高品質（需 16GB VRAM）"
echo ""
read -rp "請輸入編號 [1-4]：" CHOICE

case "$CHOICE" in
  1)
    REPO="bartowski/Qwen_Qwen3.5-9B-GGUF"
    FILE="Qwen_Qwen3.5-9B-Q5_K_M.gguf"
    SIZE="6.86 GB"
    ;;
  2)
    REPO="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
    FILE="qwen2.5-coder-7b-instruct-q8_0.gguf"
    SIZE="8.10 GB"
    ;;
  3)
    REPO="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
    FILE="qwen2.5-coder-14b-instruct-q4_k_m.gguf"
    SIZE="8.99 GB"
    ;;
  4)
    REPO="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
    FILE="qwen2.5-coder-14b-instruct-q8_0.gguf"
    SIZE="15.7 GB"
    ;;
  *)
    echo "無效選擇，離開。"
    exit 1
    ;;
esac

MODEL_PATH="$MODEL_DIR/$FILE"

echo ""
echo "=== 下載模型 ==="
echo "來源：$REPO"
echo "檔案：$FILE（$SIZE）"
echo "路徑：$MODEL_PATH"
echo ""

python3 - <<EOF
from huggingface_hub import hf_hub_download

print("開始下載，請稍候...")
path = hf_hub_download(
    repo_id="$REPO",
    filename="$FILE",
    local_dir="$MODEL_DIR",
)
print(f"\n模型已儲存至：{path}")
EOF

echo ""
echo "=== 下載完成 ==="
echo "啟動一般聊天：  bash start.sh"
echo "啟動 OpenClaw： bash start_openclaw.sh"
echo ""
echo "若要設為預設，請修改 .env："
echo "  MODEL_PATH=$MODEL_PATH"
