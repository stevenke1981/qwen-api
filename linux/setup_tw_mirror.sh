#!/bin/bash
# setup_tw_mirror.sh
# 將台灣鏡像站點加入 apt sources，作為備用來源
# 支援 Ubuntu 22.04 (jammy) / 24.04 (noble)
set -e

echo "=== 設定台灣 apt 鏡像站點 ==="
echo ""

# ── 偵測 Ubuntu 版本代號 ───────────────────────────────────────────────────────
CODENAME=$(lsb_release -cs 2>/dev/null || . /etc/os-release && echo "$VERSION_CODENAME")
echo "Ubuntu 版本：$CODENAME"

if [[ "$CODENAME" != "jammy" && "$CODENAME" != "noble" && "$CODENAME" != "focal" ]]; then
    echo "警告：未測試過的版本 ($CODENAME)，繼續執行但結果不保證"
fi

# ── 備份現有 sources.list ──────────────────────────────────────────────────────
SOURCES="/etc/apt/sources.list"
BACKUP="/etc/apt/sources.list.bak.$(date +%Y%m%d_%H%M%S)"
echo "備份原始設定 → $BACKUP"
sudo cp "$SOURCES" "$BACKUP"

# ── 寫入台灣鏡像設定 ──────────────────────────────────────────────────────────
echo ""
echo "寫入台灣鏡像站點..."

sudo tee /etc/apt/sources.list.d/tw-mirrors.list > /dev/null <<EOF
# ── 台灣鏡像站點（備用）─────────────────────────────────────────────────────
# 國立交通大學 (NCTU/NYCU)
deb http://ubuntu.cs.nctu.edu.tw/ubuntu/ ${CODENAME} main restricted universe multiverse
deb http://ubuntu.cs.nctu.edu.tw/ubuntu/ ${CODENAME}-updates main restricted universe multiverse
deb http://ubuntu.cs.nctu.edu.tw/ubuntu/ ${CODENAME}-security main restricted universe multiverse
deb http://ubuntu.cs.nctu.edu.tw/ubuntu/ ${CODENAME}-backports main restricted universe multiverse

# 國立臺灣大學 (NTU CSIE)
deb http://ubuntu.csie.ntu.edu.tw/ubuntu/ ${CODENAME} main restricted universe multiverse
deb http://ubuntu.csie.ntu.edu.tw/ubuntu/ ${CODENAME}-updates main restricted universe multiverse
deb http://ubuntu.csie.ntu.edu.tw/ubuntu/ ${CODENAME}-security main restricted universe multiverse
deb http://ubuntu.csie.ntu.edu.tw/ubuntu/ ${CODENAME}-backports main restricted universe multiverse

# 中華電信 HiNet
deb http://ftp.ubuntu-tw.org/mirror/ubuntu/ ${CODENAME} main restricted universe multiverse
deb http://ftp.ubuntu-tw.org/mirror/ubuntu/ ${CODENAME}-updates main restricted universe multiverse
deb http://ftp.ubuntu-tw.org/mirror/ubuntu/ ${CODENAME}-security main restricted universe multiverse
deb http://ftp.ubuntu-tw.org/mirror/ubuntu/ ${CODENAME}-backports main restricted universe multiverse
EOF

echo "  已寫入：/etc/apt/sources.list.d/tw-mirrors.list"

# ── 設定優先順序（讓台灣站作為備用，不搶過原始站）────────────────────────────
echo ""
echo "設定優先順序（台灣站優先級 500，低於原始站 600）..."

sudo tee /etc/apt/preferences.d/tw-mirrors > /dev/null <<EOF
# 台灣鏡像站優先級設定
# 500 = 備用（低於預設的 990，但在無法連線時自動接管）
Package: *
Pin: origin ubuntu.cs.nctu.edu.tw
Pin-Priority: 500

Package: *
Pin: origin ubuntu.csie.ntu.edu.tw
Pin-Priority: 500

Package: *
Pin: origin ftp.ubuntu-tw.org
Pin-Priority: 500
EOF

echo "  已寫入：/etc/apt/preferences.d/tw-mirrors"

# ── 更新套件清單 ──────────────────────────────────────────────────────────────
echo ""
echo "更新套件清單（apt update）..."
sudo apt-get update 2>&1 | tail -5

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 完成 ==="
echo ""
echo "台灣鏡像站點已加入，作為備用來源。"
echo ""
echo "測試連線速度（選用）："
echo "  curl -o /dev/null -s -w '%{time_total}s\n' http://ubuntu.cs.nctu.edu.tw/ubuntu/dists/${CODENAME}/Release"
echo ""
echo "還原設定："
echo "  sudo rm /etc/apt/sources.list.d/tw-mirrors.list"
echo "  sudo rm /etc/apt/preferences.d/tw-mirrors"
echo "  sudo apt-get update"
