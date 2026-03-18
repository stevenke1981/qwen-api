#!/bin/bash
# 06_convert_to_gguf.sh
# 從 HuggingFace 下載 Qwen3.5-9B（或任意 HF 模型），轉換成 GGUF 並量化
# 需要：llama.cpp 已 build（04b_build_llama_cpp.sh），Python + transformers
set -e

export PATH="$HOME/.local/bin:$PATH"

LLAMA_DIR="$HOME/llama.cpp"
MODEL_DIR="$HOME/models"
VENV_PYTHON="../.venv/bin/python3"

# ── 預設模型（可用環境變數覆寫）─────────────────────────────────────────────
HF_REPO="${HF_REPO:-Qwen/Qwen3.5-9B}"
MODEL_NAME="${MODEL_NAME:-Qwen3.5-9B}"
HF_LOCAL="$MODEL_DIR/hf_${MODEL_NAME}"   # safetensors 暫存目錄
GGUF_F16="$MODEL_DIR/${MODEL_NAME}-F16.gguf"

mkdir -p "$MODEL_DIR"

echo "=== HuggingFace → GGUF 轉換工具 ==="
echo "來源：$HF_REPO"
echo "本地暫存：$HF_LOCAL"
echo ""

# ── 步驟 1：安裝 Python 依賴 ─────────────────────────────────────────────────
echo "[1/4] 安裝 Python 依賴..."
$VENV_PYTHON -c "import transformers, torch, sentencepiece" 2>/dev/null || \
    uv pip install transformers torch sentencepiece --quiet

# convert_hf_to_gguf.py 的額外依賴
$VENV_PYTHON -c "import gguf" 2>/dev/null || \
    uv pip install gguf --quiet

echo "  依賴安裝完成"
echo ""

# ── 步驟 2：下載 HF 模型（safetensors）────────────────────────────────────────
echo "[2/4] 下載模型 $HF_REPO ..."
echo "  目標目錄：$HF_LOCAL"
echo "  （若已存在會跳過已下載的分片）"
echo ""

export HF_HUB_ENABLE_HF_TRANSFER=1
$VENV_PYTHON - <<EOF
from huggingface_hub import snapshot_download
import sys

path = snapshot_download(
    repo_id="$HF_REPO",
    local_dir="$HF_LOCAL",
    ignore_patterns=["*.bin", "*.pt", "original/*"],  # 只要 safetensors
)
print(f"  下載完成：{path}")
EOF

echo ""

# ── 步驟 3：轉換成 GGUF F16 ──────────────────────────────────────────────────
echo "[3/4] 轉換成 GGUF（F16，完整精度）..."
echo "  輸出：$GGUF_F16"

if [ -f "$GGUF_F16" ]; then
    echo "  已存在，跳過轉換。若要重新轉換請刪除：$GGUF_F16"
else
    $VENV_PYTHON "$LLAMA_DIR/convert_hf_to_gguf.py" \
        "$HF_LOCAL" \
        --outtype f16 \
        --outfile "$GGUF_F16"
    echo "  轉換完成：$GGUF_F16"
fi

echo ""

# ── 步驟 4：量化 ──────────────────────────────────────────────────────────────
echo "[4/4] 量化（選擇輸出格式）"
echo ""
echo "  1) Q4_K_M  — 最小 (~5.7 GB)，速度最快，品質略降"
echo "  2) Q5_K_M  — 均衡 (~6.9 GB)，推薦日常使用"
echo "  3) Q8_0    — 最高品質 (~9.4 GB)，近乎無損"
echo "  4) 全部量化"
echo "  5) 跳過量化（保留 F16）"
echo ""
read -rp "請輸入編號 [1-5]：" QUANT_CHOICE

quantize() {
    local TYPE=$1
    local OUT="$MODEL_DIR/${MODEL_NAME}-${TYPE}.gguf"
    if [ -f "$OUT" ]; then
        echo "  已存在，跳過：$OUT"
    else
        echo "  量化 $TYPE → $OUT ..."
        llama-quantize "$GGUF_F16" "$OUT" "$TYPE"
        echo "  完成：$OUT"
    fi
}

case "$QUANT_CHOICE" in
  1) quantize Q4_K_M ;;
  2) quantize Q5_K_M ;;
  3) quantize Q8_0   ;;
  4) quantize Q4_K_M; quantize Q5_K_M; quantize Q8_0 ;;
  5) echo "  跳過量化，使用 F16：$GGUF_F16" ;;
  *) echo "  無效選擇，跳過量化。" ;;
esac

echo ""
echo "=== 完成 ==="
echo "輸出檔案："
ls -lh "$MODEL_DIR/${MODEL_NAME}"*.gguf 2>/dev/null || true
echo ""
echo "在 .env 設定 MODEL_PATH 指向你要使用的 .gguf 檔案，再執行 bash start.sh"
