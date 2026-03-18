#!/bin/bash
# fix_xrdp.sh
# 修正 XRDP + 恢復終端登入模式
# 問題：安裝 XFCE4 後開機變成桌面登入畫面、XRDP 無法連線
# 用法：bash fix_xrdp.sh

set -e

echo "=== 修正 XRDP + 恢復終端登入 ==="
echo ""

# ── 1. 恢復開機預設為終端模式 ────────────────────────────────────────────────
echo "[1/5] 恢復開機預設為終端模式（multi-user.target）..."
sudo systemctl set-default multi-user.target
echo "  ✓ 下次開機將進入終端登入"

# ── 2. 停用 display manager（若已安裝）────────────────────────────────────────
echo ""
echo "[2/5] 停用 display manager..."
for dm in lightdm gdm3 sddm; do
    if systemctl is-enabled "$dm" &>/dev/null 2>&1; then
        sudo systemctl disable "$dm"
        sudo systemctl stop "$dm" 2>/dev/null || true
        echo "  ✓ 已停用 $dm"
    fi
done

# ── 3. 修正 /etc/xrdp/startwm.sh ─────────────────────────────────────────────
echo ""
echo "[3/5] 修正 /etc/xrdp/startwm.sh..."
sudo tee /etc/xrdp/startwm.sh > /dev/null << 'EOF'
#!/bin/sh
if [ -r /etc/default/locale ]; then
  . /etc/default/locale
  export LANG LANGUAGE
fi
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
exec startxfce4
EOF
sudo chmod +x /etc/xrdp/startwm.sh
echo "  ✓ startwm.sh 已更新"

# ── 4. 設定目前使用者的 session ───────────────────────────────────────────────
echo ""
echo "[4/5] 設定使用者 session (~/.xsession)..."
echo "startxfce4" > ~/.xsession
chmod +x ~/.xsession
echo "  ✓ ~/.xsession 已設定（使用者：$(whoami)）"

# 確保 xrdp 在 ssl-cert 群組
sudo adduser xrdp ssl-cert 2>/dev/null || true

# ── 5. 重啟 XRDP ──────────────────────────────────────────────────────────────
echo ""
echo "[5/5] 重啟 XRDP 服務..."
sudo systemctl enable xrdp
sudo systemctl restart xrdp
sleep 2
echo ""
sudo systemctl status xrdp --no-pager | head -6

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 修正完成 ==="
echo ""
IP=$(hostname -I | awk '{print $1}')
echo "XRDP 連線資訊："
echo "  位址：$IP:3389"
echo "  帳號：$(whoami)（Ubuntu 帳號密碼）"
echo "  Session：選 Xorg（不要選 Xvnc）"
echo ""
echo "建議重新開機確認終端模式："
echo "  sudo reboot"
