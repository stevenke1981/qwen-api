#!/bin/bash
set -e

echo "=== 安裝編譯工具 ==="

sudo apt-get update -q
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    ninja-build \
    pkg-config

echo ""
echo "確認版本："
gcc --version | head -1
cmake --version | head -1
echo ""
echo "=== 完成 ==="
