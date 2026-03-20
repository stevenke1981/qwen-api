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
    echo "   uv pip install torch --python "$VENV_PYTHON""
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
    uv pip install flash-attn --python "$VENV_PYTHON" --no-build-isolation
    exit 0
fi

# ── 比對 wheel ─────────────────────────────────────────────────────────────────
# CUDA 12.x wheel 向後相容，PyTorch 版本也可降版使用
# 嘗試順序：完整比對 → cu major → 降 CUDA/Torch fallback → 任意 Python 匹配

ALL_WHEELS=$(echo "$RELEASES" \
    | grep -oP '"browser_download_url":\s*"\K[^"]+\.whl' \
    | grep "linux_x86_64" || true)

find_wheel() {
    echo "$ALL_WHEELS" | grep "$1" | head -1
}

# Fallback CUDA 版本清單（從新到舊）
CUDA_FALLBACKS=("$CUDA_FULL" "$CUDA_MAJOR" "cu126" "cu124" "cu123" "cu122" "cu121" "cu118")
# Fallback PyTorch 版本清單（從新到舊）
TORCH_FALLBACKS=("$TORCH_VER" "2.7" "2.6" "2.5" "2.4" "2.3")

WHEEL_URL=""
MATCHED_DESC=""

# 嘗試 CUDA × PyTorch 組合
for CU in "${CUDA_FALLBACKS[@]}"; do
    for TV in "${TORCH_FALLBACKS[@]}"; do
        for PATTERN in \
            "${CU}torch${TV}cxx11abi${CXX_ABI}-${PY_VER}" \
            "${CU}torch${TV}-${PY_VER}"
        do
            WHEEL_URL=$(find_wheel "$PATTERN")
            if [ -n "$WHEEL_URL" ]; then
                MATCHED_DESC="$PATTERN"
                break 3
            fi
        done
    done
done

# 最後 fallback：任何符合 Python 版本的 wheel
if [ -z "$WHEEL_URL" ]; then
    WHEEL_URL=$(find_wheel "${PY_VER}-${PY_VER}-linux_x86_64")
    [ -n "$WHEEL_URL" ] && MATCHED_DESC="(best available for $PY_VER)"
fi

# ── 安裝並驗證 ────────────────────────────────────────────────────────────────
build_from_source() {
    echo ""
    echo "  從原始碼編譯 flash-attn（約 20-40 分鐘）..."
    uv pip install flash-attn --python "$VENV_PYTHON" --no-build-isolation
}

install_wheel() {
    local url="$1"
    local desc="$2"
    FA_VER=$(echo "$url" | grep -oP 'flash_attn-\K[0-9.]+')
    echo "✓ 找到預編譯 wheel：flash-attn $FA_VER  [$desc]"
    echo "  $url"
    echo ""
    uv pip install "$url" --python "$VENV_PYTHON"
    # 驗證 import（ABI 不符會 ImportError，即使安裝成功）
    if "$VENV_PYTHON" -c "import flash_attn" 2>/dev/null; then
        return 0
    else
        echo ""
        echo "  ⚠ wheel 安裝成功但 import 失敗（ABI 與 PyTorch $TORCH_VER 不相容）"
        echo "  移除並改用原始碼編譯..."
        uv pip uninstall flash-attn --python "$VENV_PYTHON" -y 2>/dev/null || true
        return 1
    fi
}

if [ -n "$WHEEL_URL" ]; then
    install_wheel "$WHEEL_URL" "$MATCHED_DESC" || build_from_source
else
    echo "⚠ 未找到符合的預編譯 wheel"
    echo "  (Python=$PY_VER  PyTorch=$TORCH_VER  CUDA=$CUDA_FULL  ABI=$CXX_ABI)"
    echo ""
    read -rp "  從原始碼編譯？（約 20-40 分鐘）[y/N]：" DO_BUILD
    if [[ "$DO_BUILD" =~ ^[Yy]$ ]]; then
        build_from_source
    else
        echo "已跳過。可稍後執行："
        echo "  bash install_flash_attn.sh"
        exit 0
    fi
fi

echo ""
"$VENV_PYTHON" -c \
    "import flash_attn; print(f'✅ flash-attn {flash_attn.__version__} 安裝成功')"
