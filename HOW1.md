# HOW1 — 模型加速 & 技術選型說明

## 1. 如何讓模型反應速度更快

模型回應速度由兩個階段決定：

| 階段 | 說明 | 瓶頸 |
|------|------|------|
| **Prefill**（prompt processing） | 將 user 輸入 encode 進 KV cache | CPU / GPU 計算量 |
| **Decode**（token generation） | 逐 token 生成回應 | GPU 記憶體頻寬 |

量化模型（Q5_K_M）的 decode 速度幾乎完全受限於 **GPU 記憶體頻寬**，而非算力。

---

### 1.1 最重要：完整 GPU offload

```env
N_GPU_LAYERS=-1   # -1 = 全部 layer 放 GPU，絕對不要縮減
```

目前 start.sh 已設定 `-1`，確認 VRAM 足夠放下 Q5_K_M（約需 6.5 GB）。
若 VRAM 不足而 offload 不完全，速度會掉 5–10 倍。

---

### 1.2 開啟 Flash Attention

Flash Attention 降低 prefill 階段的記憶體存取，對長 context 效果顯著。

```bash
# 加入 start.sh
exec llama-server \
    ...
    --flash-attn \          # ← 新增
    --chat-template chatml
```

---

### 1.3 調整 Batch Size

```env
N_BATCH=512    # 目前值
```

| 值 | 效果 |
|----|------|
| 128–256 | 適合 VRAM 較少、單請求 |
| 512 | 目前預設，均衡 |
| 1024–2048 | prefill 更快，但 VRAM 用量增加 |

若 GPU VRAM > 8 GB，可嘗試提高到 `1024`。

---

### 1.4 縮小 Context Size

```env
N_CTX=8192    # 目前值
```

KV cache 大小 ∝ N_CTX × layers × head_dim。
若實際對話很少超過 4096 tokens，改成：

```env
N_CTX=4096    # 省下約 40% KV cache VRAM，給 decode 更多頻寬
```

---

### 1.5 開啟 Continuous Batching（多用戶）

```bash
exec llama-server \
    ...
    --parallel 4 \          # 同時處理 4 個請求 slot
    --cont-batching \       # 啟用 continuous batching
```

單人使用不需要，多人共用同一台伺服器時效益明顯。

---

### 1.6 降低量化等級（速度 vs 品質取捨）

| 量化 | 模型大小 | 速度 | 品質損失 |
|------|---------|------|---------|
| Q8_0 | ~9.5 GB | 慢 | 最低 |
| **Q5_K_M** | ~6.5 GB | ⭐ 均衡 | 低（目前使用）|
| Q4_K_M | ~5.1 GB | 快 | 中 |
| Q4_0 | ~4.7 GB | 最快 | 較高 |

若可接受輕微品質下降，換成 `Q4_K_M` 可提升 decode 約 15–25%。

---

### 1.7 完整優化後的 start.sh 建議參數

```bash
exec llama-server \
    --model "$MODEL_PATH" \
    --host "$HOST" \
    --port "$PORT" \
    --n-gpu-layers -1 \
    --ctx-size 4096 \        # 視需求調整
    --batch-size 1024 \      # 從 512 提升
    --flash-attn \           # 新增
    --chat-template chatml
```

---

### 1.8 診斷：如何確認目前速度

llama-server 的 log 會輸出：

```
prompt eval time =  xxx ms /  yyy tokens  ( A ms per token,  B tokens per second)
eval time        =  xxx ms /  yyy tokens  ( A ms per token,  B tokens per second)
```

- **prompt eval（prefill）**：對話歷史越長越慢，Flash Attention 改善這裡
- **eval（decode）**：主要受 VRAM 頻寬限制，量化等級影響這裡

Qwen3.5-9B Q5_K_M 在 RTX 3080（10 GB）上 decode 約 **40–60 tok/s**。

---

## 2. 為何選 llama.cpp，不選 vLLM

### 2.1 需求對照表

| 條件 | llama.cpp ✅ | vLLM ❌ |
|------|-------------|---------|
| 消費級 GPU（8–16 GB VRAM） | 支援，GGUF 量化 | 需要 24 GB+ 跑 9B 全精度 |
| Windows / 一般 Linux | ✅ 跨平台 | ⚠️ 僅官方支援 Linux |
| GGUF 量化模型 | ✅ 原生支援 | ❌ 不支援 GGUF |
| 安裝複雜度 | 低，單一執行檔 | 高，需 Python venv + CUDA toolkit |
| 記憶體使用量 | 低（量化後 6.5 GB） | 高（全精度 ~18 GB） |
| 單人 / 小團隊使用 | ✅ 最佳化 | 過度設計 |
| CPU fallback | ✅ 支援 | ❌ 不支援 |

---

### 2.2 vLLM 的優勢（何時才應考慮）

vLLM 的核心技術是 **PagedAttention**，優勢在於：

- **高並發**：數十至數百個並發請求，KV cache 動態分頁，吞吐量遠高於 llama.cpp
- **生產規模**：雲端 API 服務、企業多用戶場景
- **大 GPU**：A100 / H100 等 80 GB VRAM，可跑全精度或 AWQ 量化

本專案使用場景：**區網內 1–5 人使用，消費級 GPU**，vLLM 的優勢無法發揮，反而帶來不必要的部署複雜度。

---

### 2.3 結論

```
本專案選擇 llama.cpp 的理由：
  ✅ Qwen3.5-9B Q5_K_M（GGUF）可在 8 GB VRAM 跑完整 GPU offload
  ✅ llama-server 提供 OpenAI 相容 API，frontend 無需修改即可接入
  ✅ 安裝部署簡單，無複雜 Python 依賴
  ✅ 區網小規模使用，不需要 vLLM 的高並發吞吐優化
```

若未來需求變成 **>10 並發用戶 + 企業級 GPU**，再評估遷移 vLLM 或 TGI（Text Generation Inference）。

---

*最後更新：2026-03-17*
