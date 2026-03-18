#!/bin/bash
# download_qwen3_coder.sh — 下載 Qwen3-Coder-Next GGUF
# 來源：https://huggingface.co/collections/Qwen/qwen3-coder-next
# 模型：Qwen3-Coder-Next 80B（coding 旗艦，支援 128k context）
# 注意：80B 模型，RTX 3060 12GB 需搭配 --n-gpu-layers 部分 offload 到 CPU
set -e

export PATH="$HOME/.local/bin:$PATH"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"
mkdir -p "$MODEL_DIR"

REPO="Qwen/Qwen3-Coder-Next-GGUF"

# ── 量化選項 ─────────────────────────────────────────────────────────────────
QUANTS=(
  "IQ2_M  | 最小  | 品質最低   | ~20 GB  | RTX 3060 需 CPU offload"
  "IQ3_M  | 極小  | 品質差     | ~28 GB  | RTX 3060 需 CPU offload"
  "Q3_K_M | 很小  | 品質勉強   | ~32 GB  | RTX 3060 需 CPU offload"
  "Q4_K_M | 小    | 品質均衡 ✅ | ~48 GB  | 需多 GPU 或大量 CPU offload"
  "Q5_K_M | 中    | 品質佳     | ~56 GB  | 需多 GPU"
  "Q8_0   | 最大  | 近乎無損   | ~85 GB  | 需多 GPU"
)

# ── 標題 ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-Coder-Next GGUF 下載工具                         ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "模型：Qwen3-Coder-Next 80B（Qwen 官方 coding 旗艦）"
echo "特點：128k context、工具呼叫、agentic coding 優化"
echo ""
echo "⚠  VRAM 警告："
echo "   RTX 3060 12GB：只有 IQ2_M/IQ3_M 可用，需 CPU offload（速度慢）"
echo "   建議硬體：24 GB+ VRAM（RTX 4090 / A100）"
echo ""
read -rp "確認繼續？[y/N]：" CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || { echo "已取消。"; exit 0; }

echo ""
echo "選擇量化方式："
for i in "${!QUANTS[@]}"; do
    IFS='|' read -r QNAME QSIZE QQDESC QVRAM QNOTE <<< "${QUANTS[$i]}"
    printf "  %d) %-8s %-6s  %-14s %-10s %s\n" \
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

# ── 下載 ─────────────────────────────────────────────────────────────────────
echo ""
echo "=== 開始下載 ==="
echo "模型：Qwen3-Coder-Next 80B"
echo "量化：$SEL_QUANT"
echo "來源：https://huggingface.co/$REPO"
echo "目標：$MODEL_DIR"
echo ""

export HF_HUB_ENABLE_HF_TRANSFER=1

../.venv/bin/python3 -c "import huggingface_hub" 2>/dev/null || \
    uv pip install huggingface_hub hf_transfer --quiet

../.venv/bin/python3 - <<PYEOF
import sys
from huggingface_hub import list_repo_files, hf_hub_download

repo   = "$REPO"
quant  = "$SEL_QUANT"
outdir = "$MODEL_DIR"

print(f"搜尋 {repo} 中的 {quant} 量化檔案...")
try:
    all_files = [f for f in list_repo_files(repo) if f.endswith(".gguf")]
except Exception as e:
    print(f"錯誤：無法讀取 repo '{repo}': {e}")
    sys.exit(1)

if not all_files:
    print(f"錯誤：找不到任何 .gguf 檔案")
    sys.exit(1)

matches = [f for f in all_files if quant.upper() in f.upper()]

if not matches:
    print(f"找不到 {quant} 量化版本。")
    print("可用的量化：")
    for f in sorted(all_files):
        print(f"  {f}")
    sys.exit(1)

if len(matches) > 1:
    print(f"發現多個分片（{len(matches)} 個），全部下載...")
    for fname in sorted(matches):
        print(f"  下載：{fname}")
        hf_hub_download(repo_id=repo, filename=fname, local_dir=outdir)
    print(f"\n✅ 全部分片儲存至：{outdir}")
else:
    fname = matches[0]
    print(f"下載：{fname}")
    path = hf_hub_download(repo_id=repo, filename=fname, local_dir=outdir)
    print(f"\n✅ 儲存至：{path}")

print("\n完成！")
PYEOF

# ── 完成提示 ──────────────────────────────────────────────────────────────────
echo ""
echo "=== 下載完成 ==="
echo ""
echo "RTX 3060 12GB 啟動範例（部分 offload，約 20 層到 GPU）："
echo ""
echo "  llama-server \\"
echo "    --model $MODEL_DIR/Qwen3-Coder-Next-${SEL_QUANT}.gguf \\"
echo "    --n-gpu-layers 20 \\"
echo "    --ctx-size 16384 \\"
echo "    --jinja"
echo ""
echo "  調整 --n-gpu-layers 使 VRAM 不超過 11 GB"
echo "  增加 --threads 16（或 CPU 核心數）加快 CPU offload 速度"
