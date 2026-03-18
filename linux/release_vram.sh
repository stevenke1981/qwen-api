#!/bin/bash
# release_vram.sh — 強制釋放 GPU VRAM
# 停止所有 llama-server / fetch_proxy 並確認 VRAM 已釋放
set -e

echo "=== 釋放 VRAM ==="
echo ""

# ── 1. 停止 llama-server ───────────────────────────────────────────────────
echo "[1/3] 停止 llama-server..."
if pgrep -x llama-server > /dev/null; then
    pkill -TERM llama-server
    sleep 2
    # 若還在就強制殺
    if pgrep -x llama-server > /dev/null; then
        pkill -KILL llama-server
        echo "  ✓ 強制終止 llama-server"
    else
        echo "  ✓ llama-server 已停止"
    fi
else
    echo "  - llama-server 未在執行"
fi

# ── 2. 停止 fetch_proxy ────────────────────────────────────────────────────
echo "[2/3] 停止 fetch_proxy..."
if pgrep -f "fetch_proxy.py" > /dev/null; then
    pkill -f "fetch_proxy.py"
    echo "  ✓ fetch_proxy 已停止"
else
    echo "  - fetch_proxy 未在執行"
fi

# ── 3. 確認 VRAM 狀態 ─────────────────────────────────────────────────────
echo "[3/3] 目前 VRAM 使用量："
sleep 1
nvidia-smi --query-gpu=name,memory.used,memory.free,memory.total \
    --format=csv,noheader,nounits | \
    awk -F',' '{
        printf "  GPU:  %s\n", $1
        printf "  Used: %4d MiB\n", $2
        printf "  Free: %4d MiB\n", $3
        printf "  Total:%4d MiB\n", $4
    }'

echo ""
echo "=== 完成 ==="
