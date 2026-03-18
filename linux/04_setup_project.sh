#!/bin/bash
set -e

export PATH="$HOME/.local/bin:/usr/local/cuda/bin:/usr/bin:/bin:$PATH"
export CUDACXX=/usr/local/cuda/bin/nvcc
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

echo "=== 安裝 Python 專案依賴 ==="

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

# 安裝 git（編譯 llama-cpp-python 需要）
echo ""
echo "[1/3] 安裝 git..."
sudo apt-get install -y git

# 建立虛擬環境
echo ""
if [ ! -d ".venv" ]; then
    echo "[2/3] 建立虛擬環境..."
    uv venv --python 3.12
else
    echo "[2/3] 虛擬環境已存在，跳過"
fi

# 安裝所有套件
echo ""
echo "[3/3] 安裝套件（llama-cpp-python 從 git 編譯，需要數分鐘）..."
CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc" \
FORCE_CMAKE=1 \
uv pip install \
    "llama-cpp-python[server] @ git+https://github.com/abetlen/llama-cpp-python.git" \
    "python-dotenv>=1.0.0" \
    "huggingface_hub>=0.23.0" \
    "hf_transfer>=0.1.8" \
    "uvicorn[standard]>=0.30.0" \
    --no-cache-dir

# 確認安裝
echo ""
echo "確認安裝結果："
.venv/bin/python3 -c "
import llama_cpp, uvicorn, dotenv, huggingface_hub
print(f'llama-cpp-python: {llama_cpp.__version__}')
print(f'uvicorn:          {uvicorn.__version__}')
print('CUDA 支援: 已啟用')
"

echo ""
echo "=== 完成 ==="
echo "執行下一步：bash 05_download_model.sh"
