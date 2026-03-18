# tmux 使用指南

tmux 讓程式在背景持續執行，遠端桌面或 SSH 斷線後不中斷，重新連線後可接回繼續操作。

---

## 安裝

```bash
sudo apt install -y tmux
```

---

## 快速啟動（常用情境）

### 啟動 OpenClaw / llama-server

```bash
# 在背景建立 session 並執行
tmux new-session -d -s openclaw 'bash ~/qwen-api/start_openclaw.sh'

# 接回查看 log
tmux attach -t openclaw
```

### 啟動聊天模式（llama-server + fetch_proxy）

```bash
tmux new-session -d -s chat 'bash ~/qwen-api/start.sh'
tmux attach -t chat
```

---

## 基本操作

### Session 管理

| 指令 | 說明 |
|------|------|
| `tmux new -s <名稱>` | 建立並進入新 session |
| `tmux new -d -s <名稱> '<指令>'` | 在背景建立 session 並執行指令 |
| `tmux attach -t <名稱>` | 接回指定 session |
| `tmux ls` | 列出所有 session |
| `tmux kill-session -t <名稱>` | 終止指定 session |
| `tmux kill-server` | 終止所有 session |

### 在 tmux 內的快捷鍵（前綴：`Ctrl+B`）

| 按鍵 | 說明 |
|------|------|
| `Ctrl+B` → `D` | 離開（detach）session，程式繼續背景執行 |
| `Ctrl+B` → `[` | 進入捲動模式（用方向鍵或 PgUp/PgDn 捲動 log） |
| `Q` | 離開捲動模式 |
| `Ctrl+B` → `C` | 在同一 session 開新視窗 |
| `Ctrl+B` → `N` / `P` | 切換到下一個 / 上一個視窗 |
| `Ctrl+B` → `&` | 關閉目前視窗（需確認） |
| `Ctrl+B` → `%` | 垂直分割視窗 |
| `Ctrl+B` → `"` | 水平分割視窗 |
| `Ctrl+B` → 方向鍵 | 切換分割視窗 |

---

## 同時開多個服務

```bash
# 在同一個 session 開兩個視窗
tmux new-session -d -s server
tmux send-keys -t server 'bash ~/qwen-api/start_openclaw.sh' Enter
tmux new-window -t server
tmux send-keys -t server 'htop' Enter
tmux attach -t server
```

---

## 開機自動啟動（搭配 systemd）

如需開機自動在背景啟動 llama-server：

```bash
sudo tee /etc/systemd/system/openclaw.service > /dev/null << EOF
[Unit]
Description=OpenClaw llama-server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/qwen-api
ExecStart=/bin/bash $HOME/qwen-api/start_openclaw.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw

# 查看 log
sudo journalctl -u openclaw -f
```

---

## 常見情境

### 遠端桌面斷線後接回

```bash
tmux ls              # 查看有哪些 session
tmux attach -t openclaw
```

### 確認 llama-server 是否還在跑

```bash
tmux ls
# 或
curl http://127.0.0.1:8000/health
```

### 停止服務

```bash
tmux kill-session -t openclaw
```
