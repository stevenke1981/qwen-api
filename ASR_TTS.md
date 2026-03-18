# Qwen3 ASR & TTS 使用指南

本文件說明 Qwen3-ASR（語音辨識）與 Qwen3-TTS（文字轉語音）兩個模型的架構、安裝流程與 API 使用方式。

---

## Qwen3-ASR 語音辨識

### 模型說明

| 項目 | 內容 |
|------|------|
| 模型 | Qwen3-ASR-0.6B / Qwen3-ASR-1.7B |
| 架構 | Transformer 多模態（基於 Qwen3-Omni） |
| 支援語言 | 30 種語言 + 22 種中文方言 |
| 輸入格式 | WAV、MP3、URL、Base64、numpy array |
| 最長音訊 | 5 分鐘（搭配 ForcedAligner） |
| 特色 | 自動語言偵測、批次推理、歌聲辨識 |
| VRAM | 0.6B ≥ 2 GB / 1.7B ≥ 4 GB |

### 支援語言

```
中文(普通話) English  日本語  한국어  Deutsch  Français
Español  Português  Русский  Italiano  Arabic  Hindi
Indonesian  Vietnamese  Thai  Turkish  Malay  Dutch
Swedish  Danish  Finnish  Polish  Czech  Filipino
Persian  Greek  Hungarian  Macedonian  Romanian
粵語 + 22 種中文方言
```

### 安裝與啟動流程

```mermaid
flowchart TD
    A([開始]) --> B[bash qwen3_asr.sh]
    B --> C{選擇模型}
    C -->|1| D[Qwen3-ASR-0.6B\n輕量快速]
    C -->|2| E[Qwen3-ASR-1.7B\n高精度 ✅]
    D & E --> F{是否需要時間戳記?}
    F -->|否| G[安裝 qwen-asr]
    F -->|是| H[安裝 qwen-asr\n+ ForcedAligner-0.6B]
    G & H --> I[下載模型到 HF 快取]
    I --> J[產生 asr_run.py]
    J --> K[執行測試推理]
    K --> L([安裝完成])

    L --> M{啟動方式}
    M -->|指令行| N[python3 asr_run.py audio.wav]
    M -->|API Server| O[bash start_asr.sh]
    O --> P[ASR API 監聽 :8002]
```

### API 流程

```mermaid
flowchart LR
    A([客戶端]) -->|POST /transcribe\nfile=audio.wav\nlanguage=Chinese| B[asr_api.py\nport 8002]
    B --> C[儲存暫存檔]
    C --> D[Qwen3ASRModel.transcribe]
    D --> E{有時間戳記?}
    E -->|否| F[回傳 JSON\ntext + language]
    E -->|是| G[回傳 JSON\ntext + language\n+ segments]
    F & G --> A

    A2([客戶端]) -->|POST /transcribe/url\nurl=https://...| B
```

### API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `POST` | `/transcribe` | 上傳音訊檔案轉錄 |
| `POST` | `/transcribe/url` | 透過 URL 轉錄 |

### 呼叫範例

```bash
# 上傳音訊檔案（自動偵測語言）
curl -X POST http://192.168.80.224:8002/transcribe \
  -F "file=@audio.wav"

# 指定語言（更快更準）
curl -X POST http://192.168.80.224:8002/transcribe \
  -F "file=@audio.wav" \
  -F "language=Chinese"

# 啟用時間戳記
curl -X POST http://192.168.80.224:8002/transcribe \
  -F "file=@audio.wav" \
  -F "language=Chinese" \
  -F "timestamps=true"

# 透過 URL
curl -X POST http://192.168.80.224:8002/transcribe/url \
  -F "url=https://example.com/audio.wav" \
  -F "language=English"
```

### 回傳格式

```json
// 一般轉錄
{
  "text": "甚至出現交易幾乎停滯的情況。",
  "language": "Chinese"
}

// 含時間戳記
{
  "text": "甚至出現交易幾乎停滯的情況。",
  "language": "Chinese",
  "segments": [
    { "text": "甚至", "start": 0.12, "end": 0.48 },
    { "text": "出現", "start": 0.50, "end": 0.86 }
  ]
}
```

### 環境變數

```bash
ASR_MODEL=Qwen/Qwen3-ASR-1.7B    # 模型名稱
ASR_TIMESTAMPS=false               # 啟用時間戳記（需先安裝 ForcedAligner）
ASR_PORT=8002                      # 監聽 Port

# 範例：切換為 0.6B 並啟用時間戳記
ASR_MODEL=Qwen/Qwen3-ASR-0.6B ASR_TIMESTAMPS=true bash start_asr.sh
```

---

## Qwen3-TTS 文字轉語音

### 模型說明

| 項目 | 內容 |
|------|------|
| 模型 | 0.6B / 1.7B，三種模式 |
| 架構 | 離散多碼本語言模型（non-DiT） |
| 支援語言 | 10 種（中英日韓德法俄葡西義） |
| 輸出格式 | WAV |
| 端到端延遲 | 97ms（串流模式） |
| VRAM | 0.6B ≥ 2 GB / 1.7B ≥ 4 GB |

### 三種模式比較

| 模式 | 模型後綴 | 說明 | 適合情境 |
|------|---------|------|---------|
| **CustomVoice** | `-CustomVoice` | 9 種精選內建音色 + 情緒指令控制 | 產品配音、助理語音 |
| **VoiceDesign** | `-VoiceDesign` | 用自然語言描述設計音色 | 客製化音色開發 |
| **Base** | `-Base` | 語音複製（3 秒參考音訊） | 複製特定人聲 |

### 內建音色（CustomVoice / VoiceDesign）

| 音色 | 語言 | 特色 |
|------|------|------|
| `Vivian` | 中文 | 明亮略帶個性的年輕女聲 |
| `Serena` | 中文 | 溫柔親切的年輕女聲 |
| `Uncle_Fu` | 中文 | 成熟男聲，低沉醇厚 |
| `Dylan` | 中文 | 北京青年男聲，清晰 |
| `Eric` | 中文 | 成都男聲，帶磁性 |
| `Ryan` | 英文 | 活力男聲，節奏感強 |
| `Aiden` | 英文 | 陽光美式男聲，清澈中頻 |
| `Ono_Anna` | 日文 | 活潑日本女聲，輕盈音色 |
| `Sohee` | 韓文 | 溫暖韓國女聲，情感豐富 |

### 安裝與啟動流程

```mermaid
flowchart TD
    A([開始]) --> B[bash qwen3_tts.sh]
    B --> C{選擇模式}

    C -->|CustomVoice| D[內建音色 + 情緒控制]
    C -->|VoiceDesign| E[自然語言設計音色]
    C -->|Base| F[語音複製\n需 3 秒參考音訊]

    D & E --> G{選擇大小}
    F --> G
    G -->|0.6B| H[VRAM ≥ 2 GB\n輕量快速]
    G -->|1.7B| I[VRAM ≥ 4 GB\n高品質 ✅]

    H & I --> J[安裝 qwen-tts]
    J --> K[下載模型到 HF 快取]
    K --> L[產生 tts_run.py]
    L --> M[執行測試合成]
    M --> N([安裝完成])

    N --> O{啟動方式}
    O -->|指令行| P[python3 tts_run.py\n文字 語言 音色]
    O -->|API Server| Q[bash start_tts.sh]
    O -->|Web UI| R[qwen-tts-demo\nport 7860]
    Q --> S[TTS API 監聽 :8003]
```

### API 流程

```mermaid
flowchart LR
    subgraph CustomVoice 模式
        A([客戶端]) -->|POST /synthesize\nJSON: text+language+speaker+instruct| B[tts_api.py\nport 8003]
        B --> C[generate_custom_voice]
        C --> D[回傳 WAV 音訊]
        D --> A
    end

    subgraph Base 語音複製模式
        A2([客戶端]) -->|POST /clone\nfile: ref_audio\nform: text+language+ref_text| B
        B --> E[generate_voice_clone]
        E --> F[回傳 WAV 音訊]
        F --> A2
    end
```

### API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `GET` | `/speakers` | 列出可用音色 |
| `GET` | `/languages` | 列出可用語言 |
| `POST` | `/synthesize` | 文字轉語音（CustomVoice / VoiceDesign 模式） |
| `POST` | `/clone` | 語音複製（Base 模式） |

### 呼叫範例

```bash
# 查詢可用音色
curl http://192.168.80.224:8003/speakers

# 合成語音（CustomVoice）
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，歡迎使用語音合成","language":"Chinese","speaker":"Vivian"}' \
  --output output.wav

# 加入情緒指令
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","language":"English","speaker":"Ryan","instruct":"Very excited tone"}' \
  --output output.wav

# 語音複製（需提供參考音訊）
curl -X POST http://192.168.80.224:8003/clone \
  -F "text=你好，這是複製的聲音" \
  -F "language=Chinese" \
  -F "ref_text=參考音訊的文字內容" \
  -F "ref_audio=@ref.wav" \
  --output output.wav

# 語音複製（使用 URL）
curl -X POST http://192.168.80.224:8003/clone \
  -F "text=Hello" \
  -F "language=English" \
  -F "ref_url=https://example.com/ref.wav" \
  --output output.wav
```

### 環境變數

```bash
TTS_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice   # 模型名稱
TTS_MODE=custom                                     # 模式：custom 或 base
TTS_PORT=8003                                       # 監聽 Port

# 範例：切換為 Base 語音複製模式
TTS_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base TTS_MODE=base bash start_tts.sh
```

---

## 完整服務架構

```mermaid
flowchart TD
    Client([Windows 瀏覽器 / 客戶端])

    Client -->|:3000| FE[前端 Chat UI\nfrontend/]
    Client -->|:8000| LLM[llama-server\nQwen3.5-9B LLM]
    Client -->|:8001| FP[fetch_proxy.py\nDuckDuckGo 搜尋]
    Client -->|:8002| ASR[asr_api.py\nQwen3-ASR 語音辨識]
    Client -->|:8003| TTS[tts_api.py\nQwen3-TTS 語音合成]

    LLM -->|工具呼叫| FP

    subgraph Ubuntu Server GPU
        LLM
        FP
        ASR
        TTS
        FE
    end
```

## 啟動順序

```bash
# LLM + 搜尋（主服務）
tmux new-session -d -s llm 'bash ~/qwen-api/start.sh'

# OpenClaw agent
tmux new-session -d -s openclaw 'bash ~/qwen-api/start_openclaw.sh'

# ASR（需先執行 qwen3_asr.sh 安裝）
tmux new-session -d -s asr 'bash ~/qwen-api/start_asr.sh'

# TTS（需先執行 qwen3_tts.sh 安裝）
tmux new-session -d -s tts 'bash ~/qwen-api/start_tts.sh'

# 查看所有服務
tmux ls
```

> **VRAM 注意**：同時跑 LLM（~7-9 GB）+ ASR（~4 GB）+ TTS（~4 GB）會超過 RTX 3060 12 GB。
> 建議依需求按需啟動，用 `bash release_vram.sh` 釋放後再切換。
