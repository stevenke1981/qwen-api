#!/bin/bash
set -e

echo "=== 安裝 CUDA Toolkit ==="

# 確認 nvidia-smi 可用
if ! command -v nvidia-smi &> /dev/null; then
    echo "錯誤：nvidia-smi 無法使用，請先執行 01_install_nvidia_driver.sh 並重開機"
    exit 1
fi

echo "GPU 資訊："
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo ""

# 加入 CUDA 官方 repository
echo "[1/4] 加入 CUDA repository..."
wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
rm cuda-keyring_1.1-1_all.deb

# 更新套件清單
echo "[2/4] 更新套件清單..."
sudo apt-get update

# 安裝 CUDA Toolkit 12.6
echo "[3/4] 安裝 CUDA Toolkit 12.6..."
sudo apt-get install -y cuda-toolkit-12-6

# 設定環境變數
echo "[4/4] 設定環境變數..."
CUDA_ENV='
# CUDA Toolkit
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH'

if ! grep -q "CUDA Toolkit" ~/.bashrc; then
    echo "$CUDA_ENV" >> ~/.bashrc
    echo "已加入 ~/.bashrc"
fi

echo ""
echo "=== 安裝完成 ==="
echo "請執行：source ~/.bashrc"
echo "驗證：nvcc --version"
echo ""
echo "執行下一步：bash 03_install_python.sh"
