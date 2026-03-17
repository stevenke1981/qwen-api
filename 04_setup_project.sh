#!/bin/bash
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:/usr/bin:/bin:$PATH"
export CUDACXX=/usr/local/cuda/bin/nvcc
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

echo "=== 安裝專案依賴 ==="

# 確認 uv
if ! command -v uv &> /dev/null; then
    echo "錯誤：請先執行 03_install_python.sh"
    exit 1
fi

# 確認 nvcc
if [ ! -f "$CUDACXX" ]; then
    echo "錯誤：找不到 nvcc，請先執行 02_install_cuda.sh"
    exit 1
fi
echo "nvcc 版本：$(nvcc --version | grep release)"

# 安裝 git（llama-cpp-python 從原始碼編譯需要）
echo ""
echo "[1/4] 安裝 git..."
sudo apt-get install -y git

# 建立虛擬環境
if [ ! -d ".venv" ]; then
    echo ""
    echo "[2/4] 建立虛擬環境..."
    uv venv --python 3.12
else
    echo "[2/4] 虛擬環境已存在，跳過"
fi

# 安裝 llama-cpp-python 最新版（從 git，支援 qwen35 架構）
echo ""
echo "[3/4] 安裝 llama-cpp-python (CUDA，從 git 編譯，需要一些時間)..."
CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc" \
FORCE_CMAKE=1 \
uv pip install \
    "llama-cpp-python[server] @ git+https://github.com/abetlen/llama-cpp-python.git" \
    --no-cache-dir

# 安裝其他依賴
echo ""
echo "[4/4] 安裝其他套件..."
uv sync --no-install-project

# 確認版本
echo ""
echo "確認安裝結果："
.venv/bin/python3 -c "
import llama_cpp
print(f'llama-cpp-python 版本: {llama_cpp.__version__}')
print('CUDA 支援: 已啟用')
"

echo ""
echo "=== 完成 ==="
echo "執行下一步：bash 05_download_model.sh"
