#!/bin/bash
# download_qwen.sh — 下載任意 Qwen 模型 GGUF 並選擇量化方式
# 來源：HuggingFace Qwen 官方 + bartowski 量化版
set -e

export PATH="$HOME/.local/bin:$PATH"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"
mkdir -p "$MODEL_DIR"

# ── 模型清單 ─────────────────────────────────────────────────────────────────
# 格式：顯示名稱|HF Repo|最低 VRAM (GB)|說明
MODELS=(
  # ── Qwen3（最新，2025）─────────────────────────────────────────────────────
  "Qwen3-0.6B-Instruct      | Qwen/Qwen3-0.6B-Instruct-GGUF          | 1  | 最小，邊緣裝置"
  "Qwen3-1.7B-Instruct      | Qwen/Qwen3-1.7B-Instruct-GGUF          | 2  | 輕量推理"
  "Qwen3-4B-Instruct        | Qwen/Qwen3-4B-Instruct-GGUF            | 3  | 平衡速度/品質"
  "Qwen3-8B-Instruct        | Qwen/Qwen3-8B-Instruct-GGUF            | 6  | 推薦日常使用"
  "Qwen3-14B-Instruct       | Qwen/Qwen3-14B-Instruct-GGUF           | 10 | 高品質推理"
  "Qwen3-32B-Instruct       | Qwen/Qwen3-32B-Instruct-GGUF           | 22 | 旗艦，需高 VRAM"
  "Qwen3-30B-A3B-Instruct   | Qwen/Qwen3-30B-A3B-Instruct-GGUF       | 20 | MoE，推理效率高"
  # ── Qwen3.5 ───────────────────────────────────────────────────────────────
  "Qwen3.5-9B               | bartowski/Qwen_Qwen3.5-9B-GGUF         | 7  | 目前預設模型"
  # ── Qwen2.5 通用 ──────────────────────────────────────────────────────────
  "Qwen2.5-3B-Instruct      | Qwen/Qwen2.5-3B-Instruct-GGUF          | 3  | 超輕量"
  "Qwen2.5-7B-Instruct      | Qwen/Qwen2.5-7B-Instruct-GGUF          | 6  | 通用穩定"
  "Qwen2.5-14B-Instruct     | Qwen/Qwen2.5-14B-Instruct-GGUF         | 10 | 通用高品質"
  "Qwen2.5-32B-Instruct     | Qwen/Qwen2.5-32B-Instruct-GGUF         | 22 | 大模型"
  "Qwen2.5-72B-Instruct     | Qwen/Qwen2.5-72B-Instruct-GGUF         | 48 | 最強通用（需多 GPU）"
  # ── Qwen2.5-Coder ─────────────────────────────────────────────────────────
  "Qwen2.5-Coder-1.5B       | Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF  | 2  | Coding 超輕量"
  "Qwen2.5-Coder-7B         | Qwen/Qwen2.5-Coder-7B-Instruct-GGUF    | 6  | Coding 推薦"
  "Qwen2.5-Coder-14B        | Qwen/Qwen2.5-Coder-14B-Instruct-GGUF   | 10 | Coding 高品質"
  "Qwen2.5-Coder-32B        | Qwen/Qwen2.5-Coder-32B-Instruct-GGUF   | 22 | Coding 旗艦"
  # ── Qwen2.5-Math ──────────────────────────────────────────────────────────
  "Qwen2.5-Math-1.5B        | Qwen/Qwen2.5-Math-1.5B-Instruct-GGUF   | 2  | 數學專用"
  "Qwen2.5-Math-7B          | Qwen/Qwen2.5-Math-7B-Instruct-GGUF     | 6  | 數學專用"
  "Qwen2.5-Math-72B         | Qwen/Qwen2.5-Math-72B-Instruct-GGUF    | 48 | 數學最強"
  # ── QwQ（推理）────────────────────────────────────────────────────────────
  "QwQ-32B                  | bartowski/QwQ-32B-GGUF                  | 22 | 深度推理 / o1 風格"
  # ── Qwen2.5-Omni（多模態）─────────────────────────────────────────────────
  "Qwen2.5-Omni-3B          | Qwen/Qwen2.5-Omni-3B-GGUF              | 3  | 多模態（文字+音訊）"
  "Qwen2.5-Omni-7B          | Qwen/Qwen2.5-Omni-7B-GGUF              | 6  | 多模態（文字+音訊）"
)

# ── 量化選項 ─────────────────────────────────────────────────────────────────
QUANTS=(
  "IQ2_M  | 最小  | 品質最低   | 約 2-3 GB/7B"
  "Q2_K   | 極小  | 品質差     | 約 2.7 GB/7B"
  "Q3_K_M | 很小  | 品質勉強   | 約 3.3 GB/7B"
  "Q4_K_M | 小    | 品質均衡 ✅ | 約 4.1 GB/7B"
  "Q5_K_M | 中    | 品質佳 ✅   | 約 4.8 GB/7B"
  "Q6_K   | 大    | 品質近無損  | 約 5.5 GB/7B"
  "Q8_0   | 最大  | 近乎無損    | 約 7.2 GB/7B"
)

# ── 顯示模型選單 ──────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Qwen 模型下載工具                               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "── Qwen3（最新）─────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs)
    DESC=$(echo "$DESC" | xargs)
    VRAM=$(echo "$VRAM" | xargs)
    if [[ "$NAME" == Qwen3* ]] && [[ "$NAME" != Qwen3.5* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
echo "── Qwen3.5 ──────────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs)
    DESC=$(echo "$DESC" | xargs)
    if [[ "$NAME" == Qwen3.5* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
echo "── Qwen2.5 通用 ─────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs)
    DESC=$(echo "$DESC" | xargs)
    if [[ "$NAME" == Qwen2.5-[0-9]* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
echo "── Qwen2.5-Coder ────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs)
    DESC=$(echo "$DESC" | xargs)
    if [[ "$NAME" == Qwen2.5-Coder* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
echo "── Qwen2.5-Math ─────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs)
    DESC=$(echo "$DESC" | xargs)
    if [[ "$NAME" == Qwen2.5-Math* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
echo "── QwQ / Omni ───────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    NAME=$(echo "$NAME" | xargs); VRAM=$(echo "$VRAM" | xargs)
    DESC=$(echo "$DESC" | xargs)
    if [[ "$NAME" == QwQ* ]] || [[ "$NAME" == Qwen2.5-Omni* ]]; then
        printf "  %2d) %-35s VRAM ≥ %s GB  %s\n" $((i+1)) "$NAME" "$VRAM" "$DESC"
    fi
done
echo ""
read -rp "請選擇模型編號 [1-${#MODELS[@]}]：" MODEL_IDX

if [[ "$MODEL_IDX" -lt 1 || "$MODEL_IDX" -gt "${#MODELS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_NAME SEL_REPO SEL_VRAM SEL_DESC <<< "${MODELS[$((MODEL_IDX-1))]}"
SEL_NAME=$(echo "$SEL_NAME" | xargs)
SEL_REPO=$(echo "$SEL_REPO" | xargs)

# ── 顯示量化選單 ──────────────────────────────────────────────────────────────
echo ""
echo "模型：$SEL_NAME"
echo ""
echo "選擇量化方式："
for i in "${!QUANTS[@]}"; do
    IFS='|' read -r QNAME QSIZE QQDESC QVRAM <<< "${QUANTS[$i]}"
    printf "  %d) %-8s %-6s  %-14s %s\n" \
        $((i+1)) \
        "$(echo "$QNAME" | xargs)" \
        "$(echo "$QSIZE" | xargs)" \
        "$(echo "$QQDESC" | xargs)" \
        "$(echo "$QVRAM" | xargs)"
done
echo ""
read -rp "請選擇量化方式 [1-${#QUANTS[@]}]：" QUANT_IDX

if [[ "$QUANT_IDX" -lt 1 || "$QUANT_IDX" -gt "${#QUANTS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_QUANT _ _ _ <<< "${QUANTS[$((QUANT_IDX-1))]}"
SEL_QUANT=$(echo "$SEL_QUANT" | xargs)

# ── 下載 ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== 開始下載 ==="
echo "模型：$SEL_NAME"
echo "量化：$SEL_QUANT"
echo "來源：https://huggingface.co/$SEL_REPO"
echo "目標：$MODEL_DIR"
echo ""

export HF_HUB_ENABLE_HF_TRANSFER=1

# 安裝 huggingface_hub（若未安裝）
.venv/bin/python3 -c "import huggingface_hub" 2>/dev/null || \
    uv pip install huggingface_hub hf_transfer --quiet

.venv/bin/python3 - <<PYEOF
import sys
from huggingface_hub import list_repo_files, hf_hub_download

repo   = "$SEL_REPO"
quant  = "$SEL_QUANT"
outdir = "$MODEL_DIR"

# 列出 repo 內所有 .gguf 檔案
print(f"搜尋 {repo} 中的 {quant} 量化檔案...")
try:
    all_files = [f for f in list_repo_files(repo) if f.endswith(".gguf")]
except Exception as e:
    print(f"錯誤：無法讀取 repo '{repo}': {e}")
    print("該模型可能尚未有 GGUF 版本，請改用 06_convert_to_gguf.sh 手動轉換。")
    sys.exit(1)

if not all_files:
    print(f"錯誤：repo '{repo}' 中找不到任何 .gguf 檔案")
    sys.exit(1)

# 尋找符合量化方式的檔案（不區分大小寫）
matches = [f for f in all_files if quant.upper() in f.upper()]

if not matches:
    print(f"找不到 {quant} 量化版本。")
    print("可用的量化：")
    for f in sorted(all_files):
        print(f"  {f}")
    sys.exit(1)

# 若有多個分片（multi-part），全部下載
if len(matches) > 1:
    print(f"發現多個分片（{len(matches)} 個），全部下載...")
    for fname in sorted(matches):
        print(f"  下載：{fname}")
        hf_hub_download(repo_id=repo, filename=fname, local_dir=outdir)
else:
    fname = matches[0]
    print(f"下載：{fname}")
    path = hf_hub_download(repo_id=repo, filename=fname, local_dir=outdir)
    print(f"\n✅ 儲存至：{path}")

print("\n完成！")
PYEOF

echo ""
echo "=== 下載完成 ==="
echo ""
echo "在 .env 設定 MODEL_PATH 後執行 bash start.sh："
ls -lh "$MODEL_DIR"/*.gguf 2>/dev/null | grep -i "$SEL_NAME" | head -5 || true
echo ""
echo "範例："
echo "  MODEL_PATH=$MODEL_DIR/$(ls "$MODEL_DIR"/*.gguf 2>/dev/null | grep -i "$(echo $SEL_QUANT | tr '[:upper:]' '[:lower:]')" | head -1 | xargs basename 2>/dev/null || echo '<filename>.gguf')"
