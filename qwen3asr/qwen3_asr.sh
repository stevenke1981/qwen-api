#!/bin/bash
# qwen3_asr.sh — Qwen3 ASR 語音辨識安裝與執行工具
# 來源：https://huggingface.co/collections/Qwen/qwen3-asr
# 功能：安裝依賴、下載模型、產生範例腳本、執行測試轉錄
# 不使用 llama-server，透過 qwen-asr Python 套件直接推理
set -e

export PATH="$HOME/.local/bin:$PATH"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"
VENV_PYTHON="../.venv/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 模型清單 ─────────────────────────────────────────────────────────────────
MODELS=(
  "Qwen3-ASR-0.6B       | Qwen/Qwen3-ASR-0.6B | 2  | 輕量快速，適合即時轉錄"
  "Qwen3-ASR-1.7B       | Qwen/Qwen3-ASR-1.7B | 4  | 高精度，推薦使用 ✅"
)

# ── 標題 ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-ASR 語音辨識安裝工具                              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "支援語言：30 種語言（含繁中、粵語）+ 22 種中文方言"
echo "輸入格式：WAV / MP3 / URL / Base64 / numpy array"
echo "特色功能：批次推理、時間戳記、歌聲辨識、自動語言偵測"
echo ""

# ── 模型選單 ──────────────────────────────────────────────────────────────────
echo "── 選擇模型 ─────────────────────────────────────────────────────────"
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC <<< "${MODELS[$i]}"
    printf "  %d) %-25s VRAM ≥ %-2s GB  %s\n" \
        $((i+1)) "$(echo "$NAME" | xargs)" "$(echo "$VRAM" | xargs)" "$(echo "$DESC" | xargs)"
done
echo ""
read -rp "請選擇模型 [1-${#MODELS[@]}]：" MODEL_IDX

if [[ "$MODEL_IDX" -lt 1 || "$MODEL_IDX" -gt "${#MODELS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_NAME SEL_REPO _ _ <<< "${MODELS[$((MODEL_IDX-1))]}"
SEL_NAME=$(echo "$SEL_NAME" | xargs)
SEL_REPO=$(echo "$SEL_REPO" | xargs)

# ── 時間戳記選項 ──────────────────────────────────────────────────────────────
echo ""
echo "── 是否啟用時間戳記（需額外下載 Qwen3-ForcedAligner-0.6B）────────────"
echo "  1) 否（只輸出文字，速度較快）"
echo "  2) 是（輸出文字 + 每個字的開始/結束時間）"
echo ""
read -rp "請選擇 [1-2]（預設 1）：" TS_CHOICE
TS_CHOICE="${TS_CHOICE:-1}"
USE_TIMESTAMPS=false
[[ "$TS_CHOICE" == "2" ]] && USE_TIMESTAMPS=true

# ── 步驟 1：安裝依賴 ──────────────────────────────────────────────────────────
echo ""
echo "[1/4] 安裝 qwen-asr 依賴..."

# 確認 .venv 存在
if [ ! -f "$VENV_PYTHON" ]; then
    echo "  建立 .venv..."
    uv venv .venv
fi

$VENV_PYTHON -c "import qwen_asr" 2>/dev/null || \
    uv pip install -U qwen-asr --quiet
echo "  ✓ qwen-asr 安裝完成"

# Flash Attention（可選，加快推理）
echo ""
read -rp "  安裝 flash-attn（加快推理，需從原始碼編譯，約 20-40 分鐘，可選擇跳過）？[y/N]：" FA_INSTALL
if [[ "$FA_INSTALL" =~ ^[Yy]$ ]]; then
    uv pip install -U flash-attn --no-build-isolation || echo "  ⚠ flash-attn 安裝失敗，繼續（可省略）"
fi

# ── 步驟 2：下載模型 ──────────────────────────────────────────────────────────
echo ""
echo "[2/4] 下載模型 $SEL_REPO ..."
echo "  （HuggingFace 會快取至 ~/.cache/huggingface，首次下載需時間）"

export HF_HUB_ENABLE_HF_TRANSFER=1
$VENV_PYTHON -c "import huggingface_hub" 2>/dev/null || \
    uv pip install huggingface_hub hf_transfer --quiet

$VENV_PYTHON - <<PYEOF
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id="$SEL_REPO")
print(f"  ✓ 模型快取至：{path}")
PYEOF

if $USE_TIMESTAMPS; then
    echo ""
    echo "  下載 ForcedAligner..."
    $VENV_PYTHON - <<PYEOF
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id="Qwen/Qwen3-ForcedAligner-0.6B")
print(f"  ✓ ForcedAligner 快取至：{path}")
PYEOF
fi

# ── 步驟 3：產生範例腳本 ──────────────────────────────────────────────────────
echo ""
echo "[3/4] 產生範例腳本..."

if $USE_TIMESTAMPS; then
    cat > "$SCRIPT_DIR/asr_run.py" << PYEOF
#!/usr/bin/env python3
"""Qwen3-ASR 語音辨識（含時間戳記）"""
import sys
import torch
from qwen_asr import Qwen3ASRModel

MODEL = "$SEL_REPO"

model = Qwen3ASRModel.from_pretrained(
    MODEL,
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_new_tokens=256,
    forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",
    forced_aligner_kwargs=dict(dtype=torch.bfloat16, device_map="cuda:0"),
)

# 用法：python3 asr_run.py <audio_file> [language]
# language 可留空（自動偵測）
# 支援：中文 English 日本語 한국어 Deutsch Français 等
audio = sys.argv[1] if len(sys.argv) > 1 else \
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_zh.wav"
language = sys.argv[2] if len(sys.argv) > 2 else None

results = model.transcribe(
    audio=audio,
    language=language,
    return_time_stamps=True,
)

for r in results:
    print(f"語言：{r.language}")
    print(f"文字：{r.text}")
    segs = getattr(r, 'segments', None)
    if segs:
        print("時間戳記：")
        for seg in segs[:5]:
            print(f"  [{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")
        if len(segs) > 5:
            print(f"  ...（共 {len(segs)} 個片段）")
PYEOF
else
    cat > "$SCRIPT_DIR/asr_run.py" << PYEOF
#!/usr/bin/env python3
"""Qwen3-ASR 語音辨識"""
import sys
import torch
from qwen_asr import Qwen3ASRModel

MODEL = "$SEL_REPO"

model = Qwen3ASRModel.from_pretrained(
    MODEL,
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_inference_batch_size=32,
    max_new_tokens=256,
)

# 用法：python3 asr_run.py <audio_file> [language]
# language 可留空（自動偵測）
# 支援：中文 English 日本語 한국어 Deutsch Français 等
audio = sys.argv[1] if len(sys.argv) > 1 else \
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_zh.wav"
language = sys.argv[2] if len(sys.argv) > 2 else None

results = model.transcribe(audio=audio, language=language)

for r in results:
    print(f"語言：{r.language}")
    print(f"文字：{r.text}")
PYEOF
fi

chmod +x "$SCRIPT_DIR/asr_run.py"
echo "  ✓ 產生 asr_run.py"

# ── 步驟 4：測試推理 ──────────────────────────────────────────────────────────
echo ""
echo "[4/4] 測試推理（使用範例音訊）..."
echo ""
$VENV_PYTHON "$SCRIPT_DIR/asr_run.py"

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 安裝完成 ==="
echo ""
echo "使用方式："
echo "  # 辨識本地檔案（自動偵測語言）"
echo "  .venv/bin/python3 asr_run.py /path/to/audio.wav"
echo ""
echo "  # 指定語言（更快更準）"
echo "  .venv/bin/python3 asr_run.py /path/to/audio.wav Chinese"
echo "  .venv/bin/python3 asr_run.py /path/to/audio.wav English"
echo ""
echo "  # 辨識 URL"
echo "  .venv/bin/python3 asr_run.py https://example.com/audio.wav"
echo ""
echo "支援語言：Chinese English Japanese Korean German French"
echo "          Spanish Portuguese Russian Italian Thai Vietnamese"
echo "          Arabic Hindi Indonesian Cantonese 等 30 種語言"
