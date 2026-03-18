#!/bin/bash
# qwen3_tts.sh — Qwen3 TTS 文字轉語音安裝與執行工具
# 來源：https://huggingface.co/collections/Qwen/qwen3-tts
# 功能：安裝依賴、下載模型、產生範例腳本、可選啟動 Web UI
# 不使用 llama-server，透過 qwen-tts Python 套件直接推理
set -e

export PATH="$HOME/.local/bin:$PATH"
VENV_PYTHON="../.venv/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 模型清單 ─────────────────────────────────────────────────────────────────
# 格式：顯示名稱|HF Repo|VRAM (GB)|說明|模型類型
MODELS=(
  "TTS-0.6B-Base        | Qwen/Qwen3-TTS-12Hz-0.6B-Base         | 2 | 輕量，語音複製（Clone）     | base"
  "TTS-1.7B-Base        | Qwen/Qwen3-TTS-12Hz-1.7B-Base         | 4 | 高品質，語音複製（Clone）✅ | base"
  "TTS-0.6B-CustomVoice | Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice  | 2 | 9 種內建音色 + 情緒控制    | custom"
  "TTS-1.7B-CustomVoice | Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice  | 4 | 9 種內建音色 + 情緒控制 ✅ | custom"
  "TTS-1.7B-VoiceDesign | Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign  | 4 | 自然語言描述設計音色        | custom"
)

# ── 內建音色清單（CustomVoice / VoiceDesign）────────────────────────────────
SPEAKERS=(
  "Vivian     | 中文  | 明亮略帶個性的年輕女聲"
  "Serena     | 中文  | 溫柔親切的年輕女聲"
  "Uncle_Fu   | 中文  | 成熟男聲，低沉醇厚"
  "Dylan      | 中文  | 北京青年男聲，清晰"
  "Eric       | 中文  | 成都男聲，帶磁性"
  "Ryan       | 英文  | 活力男聲，節奏感強"
  "Aiden      | 英文  | 陽光美式男聲，清澈中頻"
  "Ono_Anna   | 日文  | 活潑日本女聲，輕盈音色"
  "Sohee      | 韓文  | 溫暖韓國女聲，情感豐富"
)

# ── 標題 ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║          Qwen3-TTS 文字轉語音安裝工具                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "支援語言：中文 English 日本語 한국어 Deutsch Français"
echo "          Русский Português Español Italiano（共 10 種）"
echo "端到端延遲：97ms（串流模式）"
echo ""

# ── 模型選單 ──────────────────────────────────────────────────────────────────
echo "── 選擇模型 ─────────────────────────────────────────────────────────"
echo ""
echo "  Base      — 語音複製（提供 3 秒參考音訊，複製任意音色）"
echo "  CustomVoice — 9 種精選內建音色 + 自然語言情緒控制"
echo "  VoiceDesign — 用文字描述你想要的音色"
echo ""
for i in "${!MODELS[@]}"; do
    IFS='|' read -r NAME REPO VRAM DESC TYPE <<< "${MODELS[$i]}"
    printf "  %d) %-25s VRAM ≥ %-2s GB  %s\n" \
        $((i+1)) "$(echo "$NAME" | xargs)" "$(echo "$VRAM" | xargs)" "$(echo "$DESC" | xargs)"
done
echo ""
read -rp "請選擇模型 [1-${#MODELS[@]}]：" MODEL_IDX

if [[ "$MODEL_IDX" -lt 1 || "$MODEL_IDX" -gt "${#MODELS[@]}" ]] 2>/dev/null; then
    echo "無效選擇，離開。"; exit 1
fi

IFS='|' read -r SEL_NAME SEL_REPO _ _ SEL_TYPE <<< "${MODELS[$((MODEL_IDX-1))]}"
SEL_NAME=$(echo "$SEL_NAME" | xargs)
SEL_REPO=$(echo "$SEL_REPO" | xargs)
SEL_TYPE=$(echo "$SEL_TYPE" | xargs)

# ── 步驟 1：安裝依賴 ──────────────────────────────────────────────────────────
echo ""
echo "[1/4] 安裝 qwen-tts 依賴..."

if [ ! -f "$VENV_PYTHON" ]; then
    echo "  建立 .venv..."
    uv venv .venv
fi

$VENV_PYTHON -c "import qwen_tts" 2>/dev/null || \
    uv pip install -U qwen-tts --quiet
$VENV_PYTHON -c "import soundfile" 2>/dev/null || \
    uv pip install soundfile --quiet
echo "  ✓ qwen-tts 安裝完成"

echo ""
read -rp "  安裝 flash-attn（加快推理，需編譯約 5-10 分鐘）？[y/N]：" FA_INSTALL
if [[ "$FA_INSTALL" =~ ^[Yy]$ ]]; then
    uv pip install -U flash-attn --no-build-isolation || echo "  ⚠ flash-attn 安裝失敗，繼續（可省略）"
fi

# ── 步驟 2：下載模型 ──────────────────────────────────────────────────────────
echo ""
echo "[2/4] 下載模型 $SEL_REPO ..."

export HF_HUB_ENABLE_HF_TRANSFER=1
$VENV_PYTHON -c "import huggingface_hub" 2>/dev/null || \
    uv pip install huggingface_hub hf_transfer --quiet

$VENV_PYTHON - <<PYEOF
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id="$SEL_REPO")
print(f"  ✓ 模型快取至：{path}")
PYEOF

# ── 步驟 3：產生範例腳本 ──────────────────────────────────────────────────────
echo ""
echo "[3/4] 產生範例腳本..."

if [[ "$SEL_TYPE" == "base" ]]; then
    # ── Base：語音複製模式 ──────────────────────────────────────────────────
    cat > "$SCRIPT_DIR/tts_run.py" << PYEOF
#!/usr/bin/env python3
"""Qwen3-TTS 語音複製模式
用法：python3 tts_run.py "要合成的文字" [語言] [參考音訊路徑] [參考音訊文字]

範例：
  python3 tts_run.py "你好，歡迎使用語音合成" Chinese
  python3 tts_run.py "Hello world" English ref.wav "Hello I am your reference"
"""
import sys
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL = "$SEL_REPO"

# Flash Attention（若已安裝）
try:
    import flash_attn
    ATTN = "flash_attention_2"
except ImportError:
    ATTN = "eager"

model = Qwen3TTSModel.from_pretrained(
    MODEL,
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation=ATTN,
)

text     = sys.argv[1] if len(sys.argv) > 1 else "你好，這是 Qwen3 TTS 語音合成測試。"
language = sys.argv[2] if len(sys.argv) > 2 else "Chinese"
ref_audio = sys.argv[3] if len(sys.argv) > 3 else \
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav"
ref_text = sys.argv[4] if len(sys.argv) > 4 else \
    "Okay. Yeah. I resent you. I love you. I respect you."

print(f"合成文字：{text}")
print(f"語言：{language}")
print(f"參考音訊：{ref_audio}")

wavs, sr = model.generate_voice_clone(
    text=text,
    language=language,
    ref_audio=ref_audio,
    ref_text=ref_text,
)

output = "tts_output.wav"
sf.write(output, wavs[0], sr)
print(f"\n✅ 輸出：{output}（{sr} Hz）")
PYEOF

else
    # ── CustomVoice / VoiceDesign：內建音色模式 ─────────────────────────────
    echo ""
    echo "── 選擇內建音色 ─────────────────────────────────────────────────────"
    for i in "${!SPEAKERS[@]}"; do
        IFS='|' read -r SNAME SLANG SDESC <<< "${SPEAKERS[$i]}"
        printf "  %d) %-12s %-6s %s\n" \
            $((i+1)) "$(echo "$SNAME" | xargs)" "$(echo "$SLANG" | xargs)" "$(echo "$SDESC" | xargs)"
    done
    echo ""
    read -rp "請選擇預設音色 [1-${#SPEAKERS[@]}]（範例腳本使用）：" SPK_IDX
    SPK_IDX="${SPK_IDX:-1}"
    IFS='|' read -r SEL_SPEAKER _ _ <<< "${SPEAKERS[$((SPK_IDX-1))]}"
    SEL_SPEAKER=$(echo "$SEL_SPEAKER" | xargs)

    cat > "$SCRIPT_DIR/tts_run.py" << PYEOF
#!/usr/bin/env python3
"""Qwen3-TTS 內建音色模式
用法：python3 tts_run.py "要合成的文字" [語言] [音色] [情緒指令]

音色列表：Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee
語言列表：Chinese English Japanese Korean German French Russian Portuguese Spanish Italian

範例：
  python3 tts_run.py "你好，歡迎使用語音合成" Chinese Vivian
  python3 tts_run.py "你好" Chinese Vivian "用特別開心的語氣說"
  python3 tts_run.py "Hello world" English Ryan "Very excited tone"
"""
import sys
import torch
import soundfile as sf
from qwen_tts import Qwen3TTSModel

MODEL = "$SEL_REPO"

try:
    import flash_attn
    ATTN = "flash_attention_2"
except ImportError:
    ATTN = "eager"

model = Qwen3TTSModel.from_pretrained(
    MODEL,
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation=ATTN,
)

text     = sys.argv[1] if len(sys.argv) > 1 else "你好，這是 Qwen3 TTS 語音合成測試。"
language = sys.argv[2] if len(sys.argv) > 2 else "Chinese"
speaker  = sys.argv[3] if len(sys.argv) > 3 else "$SEL_SPEAKER"
instruct = sys.argv[4] if len(sys.argv) > 4 else ""

print(f"合成文字：{text}")
print(f"語言：{language}  音色：{speaker}")
if instruct:
    print(f"情緒指令：{instruct}")

wavs, sr = model.generate_custom_voice(
    text=text,
    language=language,
    speaker=speaker,
    instruct=instruct,
)

output = "tts_output.wav"
sf.write(output, wavs[0], sr)
print(f"\n✅ 輸出：{output}（{sr} Hz）")

# 查詢支援的音色和語言
# print(model.get_supported_speakers())
# print(model.get_supported_languages())
PYEOF
fi

chmod +x "$SCRIPT_DIR/tts_run.py"
echo "  ✓ 產生 tts_run.py"

# ── 步驟 4：測試推理 ──────────────────────────────────────────────────────────
echo ""
echo "[4/4] 測試推理..."
echo ""
$VENV_PYTHON "$SCRIPT_DIR/tts_run.py"

# ── Web UI 選項 ───────────────────────────────────────────────────────────────
echo ""
echo "=== 安裝完成 ==="
echo ""
echo "使用方式："
if [[ "$SEL_TYPE" == "base" ]]; then
    echo "  # 複製音色合成（需提供 3 秒參考音訊）"
    echo "  .venv/bin/python3 tts_run.py \"你好\" Chinese ref.wav \"參考音訊的文字內容\""
else
    echo "  # 使用內建音色合成"
    echo "  .venv/bin/python3 tts_run.py \"你好，歡迎使用語音合成\" Chinese Vivian"
    echo "  .venv/bin/python3 tts_run.py \"Hello world\" English Ryan \"Very excited\""
    echo ""
    echo "  # 啟動 Web UI（瀏覽器操作）"
    echo "  .venv/bin/python3 -m qwen_tts.demo $SEL_REPO --ip 0.0.0.0 --port 7860"
    echo "  # 或"
    echo "  .venv/bin/qwen-tts-demo $SEL_REPO --ip 0.0.0.0 --port 7860"
fi
echo ""
echo "輸出檔案：tts_output.wav（每次執行覆蓋）"
echo ""
echo "內建音色一覽："
for i in "${!SPEAKERS[@]}"; do
    IFS='|' read -r SNAME SLANG SDESC <<< "${SPEAKERS[$i]}"
    printf "  %-12s %-6s %s\n" \
        "$(echo "$SNAME" | xargs)" "$(echo "$SLANG" | xargs)" "$(echo "$SDESC" | xargs)"
done
