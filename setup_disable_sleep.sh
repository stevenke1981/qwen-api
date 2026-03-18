#!/bin/bash
# setup_disable_sleep.sh
# 停用 Ubuntu Server 休眠 / 睡眠 / 螢幕保護
# 適用於遠端桌面（XRDP）環境，防止閒置時斷線
set -e

echo "=== 停用 Ubuntu 休眠與睡眠 ==="
echo ""

# ── 1. systemd：遮蔽所有休眠目標 ─────────────────────────────────────────────
echo "[1/4] 停用 systemd 休眠目標..."
sudo systemctl mask \
    sleep.target \
    suspend.target \
    hibernate.target \
    hybrid-sleep.target \
    suspend-then-hibernate.target
echo "  已遮蔽所有休眠目標"

# ── 2. 修改 systemd sleep 設定 ────────────────────────────────────────────────
echo ""
echo "[2/4] 設定 /etc/systemd/sleep.conf..."
sudo tee /etc/systemd/sleep.conf > /dev/null <<EOF
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
EOF
sudo systemctl restart systemd-logind
echo "  sleep.conf 已更新"

# ── 3. 關閉 logind 閒置自動睡眠 ───────────────────────────────────────────────
echo ""
echo "[3/4] 關閉 logind 閒置休眠..."
LOGIND_CONF="/etc/systemd/logind.conf"
sudo sed -i 's/^#*IdleAction=.*/IdleAction=ignore/'         "$LOGIND_CONF"
sudo sed -i 's/^#*IdleActionSec=.*/IdleActionSec=0/'        "$LOGIND_CONF"
sudo sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/'       "$LOGIND_CONF"
sudo sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' "$LOGIND_CONF"
# 若設定不存在則附加
grep -q "^IdleAction=" "$LOGIND_CONF"     || echo "IdleAction=ignore"          | sudo tee -a "$LOGIND_CONF" > /dev/null
grep -q "^HandleLidSwitch=" "$LOGIND_CONF" || echo "HandleLidSwitch=ignore"    | sudo tee -a "$LOGIND_CONF" > /dev/null
sudo systemctl restart systemd-logind
echo "  logind.conf 已更新"

# ── 4. XFCE4 電源設定（若在桌面環境下執行）──────────────────────────────────
echo ""
echo "[4/4] 套用 XFCE4 電源設定..."
if command -v xfconf-query &>/dev/null && [ -n "$DISPLAY" ]; then
    # 關閉螢幕保護
    xfconf-query -c xfce4-screensaver -p /saver/enabled     -s false --create -t bool 2>/dev/null || true
    xfconf-query -c xfce4-screensaver -p /lock/enabled      -s false --create -t bool 2>/dev/null || true
    # 電源管理：不休眠
    xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/inactivity-on-ac      -s 0 --create -t int 2>/dev/null || true
    xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/inactivity-on-battery -s 0 --create -t int 2>/dev/null || true
    xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/dpms-enabled          -s false --create -t bool 2>/dev/null || true
    echo "  XFCE4 電源設定已套用"
else
    echo "  （未偵測到 XFCE4 桌面環境，跳過）"
    echo "  登入遠端桌面後再執行一次本腳本可套用 XFCE4 設定"
fi

# ── 5. X11 螢幕保護（若有 DISPLAY）──────────────────────────────────────────
if [ -n "$DISPLAY" ] && command -v xset &>/dev/null; then
    xset s off        # 關閉螢幕保護程式
    xset -dpms        # 關閉 DPMS 節電
    xset s noblank    # 不清空畫面
    echo "  X11 螢幕保護已關閉"
fi

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 完成 ==="
echo ""
echo "確認狀態："
systemctl status sleep.target --no-pager 2>&1 | grep -E "Loaded|Active" | head -2
echo ""
echo "重開機後仍然有效。"
echo "若遠端桌面仍然斷線，請確認 XRDP 的 idle timeout："
echo "  sudo nano /etc/xrdp/xrdp.ini  # 找 idle_timeout_s，設為 0"
