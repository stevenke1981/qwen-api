#!/bin/bash
set -e

echo "=== 安裝 Python (使用 uv) ==="

# 安裝 uv
echo "[1/3] 安裝 uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "uv 版本："
uv --version

# 安裝 Python 3.12
echo ""
echo "[2/3] 安裝 Python 3.12..."
uv python install 3.12

# 建立虛擬環境
echo ""
echo "[3/3] 建立虛擬環境..."
uv venv --python 3.12

# 加入 PATH
UV_ENV='
# uv
export PATH="$HOME/.local/bin:$PATH"'

if ! grep -q '\.local/bin' ~/.bashrc; then
    echo "$UV_ENV" >> ~/.bashrc
    echo "已加入 ~/.bashrc"
fi

echo ""
echo "=== 完成 ==="
echo "執行下一步：bash 04_setup_project.sh"
