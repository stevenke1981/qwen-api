#!/bin/bash
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:/usr/bin:/bin:$PATH"
export CUDACXX=/usr/local/cuda/bin/nvcc
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

INSTALL_DIR="$HOME/llama.cpp"

echo "=== 編譯 llama.cpp 二進位檔 (CUDA) ==="

# 確認 nvcc
if [ ! -f "$CUDACXX" ]; then
    echo "錯誤：找不到 nvcc，請先執行 02_install_cuda.sh"
    exit 1
fi
echo "nvcc 版本：$(nvcc --version | grep release)"

# 安裝編譯依賴
echo ""
echo "[1/4] 安裝編譯工具..."
sudo apt-get install -y git cmake build-essential

# Clone 或更新 llama.cpp
echo ""
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[2/4] 更新 llama.cpp..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "[2/4] 下載 llama.cpp..."
    git clone https://github.com/ggerganov/llama.cpp "$INSTALL_DIR"
fi

# 編譯
echo ""
echo "[3/4] 編譯（CUDA 加速，需要數分鐘）..."
cmake -B "$INSTALL_DIR/build" "$INSTALL_DIR" \
    -DGGML_CUDA=ON \
    -DCMAKE_CUDA_COMPILER="$CUDACXX" \
    -DCMAKE_BUILD_TYPE=Release
cmake --build "$INSTALL_DIR/build" --config Release -j"$(nproc)"

# 安裝到 ~/.local/bin
echo ""
echo "[4/4] 安裝二進位檔到 ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
for bin in llama-cli llama-server llama-bench llama-quantize; do
    src="$INSTALL_DIR/build/bin/$bin"
    if [ -f "$src" ]; then
        cp "$src" "$HOME/.local/bin/$bin"
        echo "  已安裝：$bin"
    fi
done

echo ""
echo "確認版本："
"$HOME/.local/bin/llama-cli" --version 2>&1 | head -1

echo ""
echo "=== 完成 ==="
echo "二進位檔位置：~/.local/bin/llama-{cli,server,bench,quantize}"
