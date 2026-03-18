#!/bin/bash
# 07_setup_remote_desktop.sh
# Ubuntu Server 安裝遠端桌面環境
# 桌面：XFCE4（輕量，適合 GPU server）
# 協定：XRDP（Windows 遠端桌面直連，不需額外軟體）
set -e

echo "=== 安裝 XFCE4 遠端桌面環境 ==="
echo "桌面：XFCE4"
echo "協定：XRDP (port 3389)"
echo ""

# ── 1. 更新套件清單 ────────────────────────────────────────────────────────────
echo "[1/6] 更新套件清單..."
sudo apt-get update -y

# ── 2. 安裝 XFCE4 桌面環境 ────────────────────────────────────────────────────
echo ""
echo "[2/6] 安裝 XFCE4 桌面環境..."
sudo apt-get install -y \
    xfce4 \
    xfce4-goodies \
    xfce4-terminal \
    xfce4-taskmanager \
    thunar \
    dbus-x11 \
    x11-xserver-utils \
    xorg

# ── 3. 安裝 XRDP ──────────────────────────────────────────────────────────────
echo ""
echo "[3/6] 安裝 XRDP..."
sudo apt-get install -y xrdp

# ── 4. 設定 XRDP 使用 XFCE4 ──────────────────────────────────────────────────
echo ""
echo "[4/6] 設定 XRDP 使用 XFCE4..."

# 全域設定（所有使用者）
echo "startxfce4" | sudo tee /etc/xrdp/startwm.sh > /dev/null
sudo chmod +x /etc/xrdp/startwm.sh

# 當前使用者設定
echo "startxfce4" > ~/.xsession
chmod +x ~/.xsession

# 修正 XRDP 顏色深度與解析度問題
sudo sed -i 's/max_bpp=32/max_bpp=24/' /etc/xrdp/xrdp.ini 2>/dev/null || true
sudo sed -i 's/#xserverbpp=24/xserverbpp=24/' /etc/xrdp/xrdp.ini 2>/dev/null || true

# 將 xrdp 加入 ssl-cert 群組（避免 TLS 憑證錯誤）
sudo adduser xrdp ssl-cert 2>/dev/null || true

# ── 5. 啟動並設定開機自啟 ──────────────────────────────────────────────────────
echo ""
echo "[5/6] 啟動 XRDP 服務..."
sudo systemctl enable xrdp
sudo systemctl restart xrdp

# ── 6. 防火牆開放 3389 ────────────────────────────────────────────────────────
echo ""
echo "[6/6] 開放防火牆 port 3389..."
if command -v ufw &>/dev/null; then
    sudo ufw allow 3389/tcp
    echo "  ufw: 已開放 3389/tcp"
else
    echo "  ufw 未安裝，請手動開放 port 3389"
fi

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 安裝完成 ==="
echo ""
echo "XRDP 狀態："
sudo systemctl status xrdp --no-pager | head -5
echo ""

# 取得 IP
IP=$(hostname -I | awk '{print $1}')
echo "連線資訊："
echo "  位址：$IP:3389"
echo "  帳號：$(whoami)（你的 Ubuntu 帳號密碼）"
echo ""
echo "Windows 連線方式："
echo "  開始 → 遠端桌面連線 → 輸入 $IP → 連線"
echo ""
echo "注意事項："
echo "  - 登入時選擇 Session: Xorg（不要選 Xvnc）"
echo "  - 若畫面黑屏，執行：echo 'startxfce4' > ~/.xsession"
echo "  - 若需多人同時連線，安裝 xrdp-multi: sudo apt install xrdp"
