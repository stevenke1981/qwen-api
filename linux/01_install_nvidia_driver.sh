#!/bin/bash
set -e

echo "=== 安裝 NVIDIA 驅動 ==="

# 確認系統
if ! command -v ubuntu-drivers &> /dev/null; then
    echo "[1/3] 安裝 ubuntu-drivers..."
    sudo apt-get update -qq
    sudo apt-get install -y ubuntu-drivers-common
else
    echo "[1/3] ubuntu-drivers 已存在"
fi

# 安裝推薦驅動
echo ""
echo "[2/3] 安裝推薦 NVIDIA 驅動..."
sudo ubuntu-drivers autoinstall

# 設定開機載入
echo ""
echo "[3/3] 確認驅動設定..."
sudo modprobe nvidia 2>/dev/null || true

echo ""
echo "=== 安裝完成 ==="
echo "請重新開機後確認："
echo "  nvidia-smi"
echo ""
echo "重開機後執行下一步：bash 02_install_cuda.sh"
