#!/bin/bash
# install_flash_attn.sh — 自動偵測版本安裝 flash-attn 預編譯 wheel
# 來源：https://github.com/Dao-AILab/flash-attention/releases
# 適用：Ubuntu / Linux x86_64
set -e

export PATH="$HOME/.local/bin:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${1:-$SCRIPT_DIR/../.venv/bin/python3}"

# ── 標題 ──────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║        flash-attn 自動安裝工具（預編譯 Wheel）                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# ── 確認 venv ─────────────────────────────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 找不到 $VENV_PYTHON"
    echo "   請先執行 qwen3_tts.sh 建立虛擬環境，或傳入路徑："
    echo "   bash install_flash_attn.sh /path/to/venv/bin/python3"
    exit 1
fi

# ── 已安裝則跳過 ──────────────────────────────────────────────────────────────
if "$VENV_PYTHON" -c "import flash_attn" 2>/dev/null; then
    FA_VER=$("$VENV_PYTHON" -c "import flash_attn; print(flash_attn.__version__)")
    echo "✅ flash-attn $FA_VER 已安裝，無需重複安裝。"
    exit 0
fi

# ── 偵測版本 ──────────────────────────────────────────────────────────────────
echo "偵測環境版本..."

PY_VER=$("$VENV_PYTHON" -c \
    "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')")

TORCH_VER=$("$VENV_PYTHON" -c \
    "import torch; v=torch.__version__.split('+')[0].split('.'); print(f'{v[0]}.{v[1]}')" \
    2>/dev/null || echo "")

CUDA_FULL=$("$VENV_PYTHON" -c \
    "import torch; v=torch.version.cuda.split('.'); print(f'cu{v[0]}{v[1]}')" \
    2>/dev/null || echo "")

CUDA_MAJOR=$("$VENV_PYTHON" -c \
    "import torch; print(f'cu{torch.version.cuda.split(\".\")[0]}')" \
    2>/dev/null || echo "")

CXX_ABI=$("$VENV_PYTHON" -c \
    "import torch; print('TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE')" \
    2>/dev/null || echo "TRUE")

if [ -z "$TORCH_VER" ] || [ -z "$CUDA_FULL" ]; then
    echo "❌ 無法偵測 PyTorch / CUDA 版本，請確認 torch 已安裝在 venv 中："
    echo "   $VENV_PYTHON -m pip install torch"
    exit 1
fi

echo "  Python   : $PY_VER"
echo "  PyTorch  : $TORCH_VER"
echo "  CUDA     : $CUDA_FULL  (major: $CUDA_MAJOR)"
echo "  CXX11ABI : $CXX_ABI"
echo ""

# ── 搜尋 GitHub Releases ──────────────────────────────────────────────────────
echo "搜尋 flash-attn 最新 release..."

RELEASES=$(curl -sf \
    "https://api.github.com/repos/Dao-AILab/flash-attention/releases?per_page=5" \
    2>/dev/null || echo "")

if [ -z "$RELEASES" ]; then
    echo "⚠ 無法連線 GitHub API（網路或限速），改用原始碼編譯..."
    "$VENV_PYTHON" -m pip install flash-attn --no-build-isolation
    exit 0
fi

# ── 比對 wheel ─────────────────────────────────────────────────────────────────
# 嘗試順序：完整 CUDA 版本 → 主版本號 → 不含 ABI（fallback）
find_wheel() {
    local pattern="$1"
    echo "$RELEASES" \
        | grep -oP '"browser_download_url":\s*"\K[^"]+\.whl' \
        | grep "$pattern" \
        | head -1
}

WHEEL_URL=""
for CU in "$CUDA_FULL" "$CUDA_MAJOR"; do
    PATTERN="${CU}torch${TORCH_VER}cxx11abi${CXX_ABI}-${PY_VER}"
    WHEEL_URL=$(find_wheel "$PATTERN")
    [ -n "$WHEEL_URL" ] && break
    # 嘗試不帶 cxx11abi 欄位
    PATTERN="${CU}torch${TORCH_VER}-${PY_VER}"
    WHEEL_URL=$(find_wheel "$PATTERN")
    [ -n "$WHEEL_URL" ] && break
done

# ── 安裝 ──────────────────────────────────────────────────────────────────────
if [ -n "$WHEEL_URL" ]; then
    FA_VER=$(echo "$WHEEL_URL" | grep -oP 'flash_attn-\K[0-9.]+')
    echo "✓ 找到預編譯 wheel：flash-attn $FA_VER"
    echo "  $WHEEL_URL"
    echo ""
    "$VENV_PYTHON" -m pip install "$WHEEL_URL"
else
    echo "⚠ 未找到符合的預編譯 wheel"
    echo "  (Python=$PY_VER  PyTorch=$TORCH_VER  CUDA=$CUDA_FULL  ABI=$CXX_ABI)"
    echo ""
    read -rp "  從原始碼編譯？（約 20-40 分鐘）[y/N]：" DO_BUILD
    if [[ "$DO_BUILD" =~ ^[Yy]$ ]]; then
        "$VENV_PYTHON" -m pip install flash-attn --no-build-isolation
    else
        echo "已跳過。可稍後執行："
        echo "  bash install_flash_attn.sh"
        exit 0
    fi
fi

echo ""
"$VENV_PYTHON" -c \
    "import flash_attn; print(f'✅ flash-attn {flash_attn.__version__} 安裝成功')"
