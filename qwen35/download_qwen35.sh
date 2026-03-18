#!/bin/bash
# download_qwen35.sh — 下載 Qwen3.5 系列模型（safetensors → GGUF 轉換）
# 來源：https://huggingface.co/collections/Qwen/qwen35
# 注意：Qwen3.5 官方尚無預製 GGUF，需本地轉換（需 llama.cpp + Python）
# 前置：bash 04b_build_llama_cpp.sh（提供 llama-quantize）
set -e

export PATH="$HOME/.local/bin:$PATH"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
VENV_PYTHON="../.venv/bin/python3"
mkdir -p "$MODEL_DIR"

# ── 模型清單 ─────────────────────────────────────────────────────────────────
# 格式：顯示名稱|HF Repo|最低 VRAM (GB)|說明
MODELS=(
  "Qwen3.5-0.8B          | Qwen/Qwen3.5-0.8B      | 1  | 超輕量，邊緣裝置"
  "Qwen3.5-0.8B-Base     | Qwen/Qwen3.5-0.8B-Base | 1  | 基礎模型（無 instruct 微調）"
  "Qwen3.5-2B            | Qwen/Qwen3.5-2B        | 2  | 輕量推理"
  "Qwen3.5-2B-Base       | Qwen/Qwen3.5-2B-Base   | 2  | 基礎模型"
  "Qwen3.5-4B            | Qwen/Qwen3.5-4B        | 3  | 平衡速度/品質"
  "Qwen3.5-4B-Base       | Qwen/Qwen3.5-4B-Base   | 3  | 基礎模型"
  "Qwen3.5-9B            | Qwen/Qwen3.5-9B        | 7  | 推薦日常使用 ✅（目前預設）"
  "Qwen3.5-9B-Base       | Qwen/Qwen3.5-9B-Base   | 7  | 基礎模型"
  "Qwen3.5-27B           | Qwen/Qwen3.5-27B       | 16 | 高品質，需 CPU offload on 12GB"
  "Qwen3.5-35B-A3B (MoE) | Qwen/Qwen3.5-35B-A3B  | 20 | MoE，推理效率高，需 CPU offload"
)

# ── 量化選項 ─────────────────────────────────────────────────────────────────
QUANTS=(
  "Q3_K_M | 很小  | 品質勉強   | 約 3.3 GB/7B  | 速度最快"
  "Q4_K_M | 小    | 品質均衡 ✅ | 約 4.1 GB/7B  | 推薦"
  "Q5_K_M | 中    | 品質佳 ✅   | 約 4.8 GB/7B  | 推薦高品質"
  "Q8_0   | 最大  | 近乎無損   | 約 7.2 GB/7B  | 最高品質"
  "全部    |       |            |               | Q3_K_M + Q4_K_M + Q5_K_M + Q8_0"
)

# ── 標題 ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3.5 系列下載 + GGUF 轉換工具                       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "注意：Qwen3.5 官方無預製 GGUF，本腳本將："
echo "  1. 下載 HuggingFace safetensors"
echo "  2. 轉換成 GGUF F16（需 llama.cpp）"
echo "  3. 量化成指定格式"
echo ""
echo "前置需求："
echo "  - bash 04b_build_llama_cpp.sh（已完成）"
echo "  - 磁碟空間：F16 約 18GB(9B) / 55GB(27B)，需預留 30%+ 空間"
echo ""

# ── 模型選單 ──────────────────────────────────────────────────────────────────
echo "── 選擇模型 ─────────────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs); DESC=$(echo "$DESC" | xargs)
    printf "  %2d) %-25s VRAM ≥ %-3s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
done
echo ""
read -rp "請選擇模型編號 [1-${#MODELS[@]}]：" MODEL_IDX

if [[ "$MODEL_IDX" -lt 1 || "$MODEL_IDX" -gt "${#MODELS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_NAME SEL_REPO _ _ <<< "${MODELS[$((MODEL_IDX-1))]}"
SEL_NAME=$(echo "$SEL_NAME" | xargs)
SEL_REPO=$(echo "$SEL_REPO" | xargs)
# 去除空格用於檔名
MODEL_NAME=$(echo "$SEL_REPO" | sed 's|Qwen/||')

# ── 量化選單 ──────────────────────────────────────────────────────────────────
echo ""
echo "模型：$SEL_NAME"
echo ""
echo "選擇量化方式："
for i in "${!QUANTS[@]}"; do
    IFS='|' read -r QNAME QSIZE QQDESC QVRAM QNOTE <<< "${QUANTS[$i]}"
    printf "  %d) %-8s %-6s  %-14s %-16s %s\n" \
        $((i+1)) \
        "$(echo "$QNAME" | xargs)" \
        "$(echo "$QSIZE" | xargs)" \
        "$(echo "$QQDESC" | xargs)" \
        "$(echo "$QVRAM" | xargs)" \
        "$(echo "$QNOTE" | xargs)"
done
echo ""
read -rp "請選擇量化方式 [1-${#QUANTS[@]}]：" QUANT_IDX

if [[ "$QUANT_IDX" -lt 1 || "$QUANT_IDX" -gt "${#QUANTS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_QUANT _ _ _ _ <<< "${QUANTS[$((QUANT_IDX-1))]}"
SEL_QUANT=$(echo "$SEL_QUANT" | xargs)

HF_LOCAL="$MODEL_DIR/hf_${MODEL_NAME}"
GGUF_F16="$MODEL_DIR/${MODEL_NAME}-F16.gguf"

# ── 確認 llama.cpp ────────────────────────────────────────────────────────────
if [ ! -f "$LLAMA_DIR/convert_hf_to_gguf.py" ]; then
    echo ""
    echo "❌ 找不到 $LLAMA_DIR/convert_hf_to_gguf.py"
    echo "   請先執行：bash 04b_build_llama_cpp.sh"
    exit 1
fi
if ! command -v llama-quantize &>/dev/null; then
    echo ""
    echo "❌ 找不到 llama-quantize"
    echo "   請先執行：bash 04b_build_llama_cpp.sh"
    exit 1
fi

# ── 步驟 1：安裝 Python 依賴 ──────────────────────────────────────────────────
echo ""
echo "[1/4] 安裝 Python 依賴..."
$VENV_PYTHON -c "import transformers, sentencepiece" 2>/dev/null || \
    uv pip install transformers sentencepiece --quiet
$VENV_PYTHON -c "import gguf" 2>/dev/null || \
    uv pip install gguf --quiet
$VENV_PYTHON -c "import huggingface_hub" 2>/dev/null || \
    uv pip install huggingface_hub hf_transfer --quiet
echo "  ✓ 依賴安裝完成"

# ── 步驟 2：下載 safetensors ──────────────────────────────────────────────────
echo ""
echo "[2/4] 下載 $SEL_REPO ..."
echo "  目標：$HF_LOCAL"
echo "  （若已下載會跳過）"

export HF_HUB_ENABLE_HF_TRANSFER=1

$VENV_PYTHON - <<PYEOF
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id="$SEL_REPO",
    local_dir="$HF_LOCAL",
    ignore_patterns=["*.bin", "*.pt", "original/*", "*.msgpack"],
)
print(f"  ✓ 下載完成：{path}")
PYEOF

# ── 步驟 3：轉換 GGUF F16 ────────────────────────────────────────────────────
echo ""
echo "[3/4] 轉換成 GGUF F16..."
echo "  輸出：$GGUF_F16"

if [ -f "$GGUF_F16" ]; then
    echo "  ✓ 已存在，跳過（刪除可重新轉換：rm $GGUF_F16）"
else
    $VENV_PYTHON "$LLAMA_DIR/convert_hf_to_gguf.py" \
        "$HF_LOCAL" \
        --outtype f16 \
        --outfile "$GGUF_F16"
    echo "  ✓ 轉換完成：$GGUF_F16"
fi

# ── 步驟 4：量化 ──────────────────────────────────────────────────────────────
echo ""
echo "[4/4] 量化..."

quantize() {
    local TYPE=$1
    local OUT="$MODEL_DIR/${MODEL_NAME}-${TYPE}.gguf"
    if [ -f "$OUT" ]; then
        echo "  ✓ 已存在，跳過：$OUT"
    else
        echo "  量化 $TYPE → $(basename $OUT) ..."
        llama-quantize "$GGUF_F16" "$OUT" "$TYPE"
        echo "  ✓ 完成：$OUT"
    fi
}

case "$SEL_QUANT" in
  Q3_K_M) quantize Q3_K_M ;;
  Q4_K_M) quantize Q4_K_M ;;
  Q5_K_M) quantize Q5_K_M ;;
  Q8_0)   quantize Q8_0   ;;
  全部)   quantize Q3_K_M; quantize Q4_K_M; quantize Q5_K_M; quantize Q8_0 ;;
  *)      echo "  無效量化選項，跳過。" ;;
esac

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 完成 ==="
echo ""
echo "輸出檔案："
ls -lh "$MODEL_DIR/${MODEL_NAME}"*.gguf 2>/dev/null || true
echo ""
echo "更新 .env 使用新模型："
echo "  MODEL_PATH=$MODEL_DIR/${MODEL_NAME}-${SEL_QUANT}.gguf"
echo ""
echo "或直接啟動："
echo "  MODEL_PATH=$MODEL_DIR/${MODEL_NAME}-${SEL_QUANT}.gguf bash start.sh"
