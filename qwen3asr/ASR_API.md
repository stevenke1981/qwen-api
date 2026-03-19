# Qwen3-ASR API 文件

**Base URL:** `http://192.168.80.224:8002`

---

## 認證模式

| 模式 | 設定方式 | 說明 |
|------|----------|------|
| 無驗證 | 不設 env var | 本機開發，所有請求均允許 |
| 單 Key | `API_KEY=sk-xxx` | 單一 secret key |
| 多 Key | `API_KEYS=sk-a,sk-b,sk-c` | 多使用者各自有 key（優先於 API_KEY） |

認證方式（二擇一，效果相同）：
```
X-API-Key: sk-your-key          # 自訂 Header（推薦）
Authorization: Bearer sk-your-key  # OpenAI 相容格式
```

`/health` 永遠不需驗證。

---

## 端點總覽

| 方法 | 路徑 | 說明 | 需驗證 |
|------|------|------|--------|
| `GET` | `/health` | 健康檢查 | 否 |
| `POST` | `/transcribe` | 上傳音訊檔案辨識 | 是（若啟用） |
| `POST` | `/transcribe/url` | 透過 URL 辨識 | 是（若啟用） |
| `POST` | `/v1/audio/transcriptions` | OpenAI Whisper 相容格式 | 是（若啟用） |

---

## GET /health

確認服務狀態與載入的模型。

**回傳範例：**
```json
{
  "status": "ok",
  "model": "Qwen/Qwen3-ASR-1.7B",
  "timestamps": false,
  "auth": "enabled"
}
```

---

## POST /transcribe

上傳音訊檔案進行語音辨識。

**Content-Type:** `multipart/form-data`

### 參數

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `file` | binary | ✅ | 音訊檔案（WAV / MP3 / M4A） |
| `language` | string | ❌ | 語言（留空自動偵測） |
| `timestamps` | bool | ❌ | `true` 啟用時間戳記 |

### 支援語言值

```
Chinese  English  Japanese  Korean  German  French
Spanish  Portuguese  Russian  Italian  Arabic  Hindi
Indonesian  Vietnamese  Thai  Turkish  Malay  Dutch
Swedish  Danish  Finnish  Polish  Czech  Filipino
Persian  Greek  Hungarian  Macedonian  Romanian  Cantonese
```

### 回傳格式

**一般：**
```json
{ "text": "甚至出現交易幾乎停滯的情況。", "language": "Chinese" }
```

**含時間戳記：**
```json
{
  "text": "甚至出現交易幾乎停滯的情況。",
  "language": "Chinese",
  "segments": [
    { "text": "甚至", "start": 0.12, "end": 0.48 }
  ]
}
```

### curl 範例

```bash
# 無驗證
curl -X POST http://192.168.80.224:8002/transcribe \
  -F "file=@audio.wav" -F "language=Chinese"

# 有驗證（X-API-Key）
curl -X POST http://192.168.80.224:8002/transcribe \
  -H "X-API-Key: sk-your-key" \
  -F "file=@audio.wav" -F "language=Chinese"

# 有驗證（Bearer）
curl -X POST http://192.168.80.224:8002/transcribe \
  -H "Authorization: Bearer sk-your-key" \
  -F "file=@audio.wav" -F "language=Chinese"

# 含時間戳記
curl -X POST http://192.168.80.224:8002/transcribe \
  -H "X-API-Key: sk-your-key" \
  -F "file=@audio.wav" -F "language=Chinese" -F "timestamps=true"
```

---

## POST /transcribe/url

透過音訊 URL 進行辨識。

**Content-Type:** `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `url` | string | ✅ | 公開音訊 URL |
| `language` | string | ❌ | 語言 |
| `timestamps` | bool | ❌ | 時間戳記 |

```bash
curl -X POST http://192.168.80.224:8002/transcribe/url \
  -H "X-API-Key: sk-your-key" \
  -F "url=https://example.com/audio.wav" \
  -F "language=English"
```

---

## POST /v1/audio/transcriptions（OpenAI 相容）

與 OpenAI Whisper API 格式相同，可直接使用 openai SDK。

**Content-Type:** `multipart/form-data`

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `file` | binary | ✅ | 音訊檔案 |
| `model` | string | ❌ | 任意字串（預設 `whisper-1`，忽略） |
| `language` | string | ❌ | 語言 |
| `response_format` | string | ❌ | `json`（預設）/ `text` / `verbose_json` |
| `timestamp_granularities` | string | ❌ | `word` / `segment` 啟用時間戳記 |

### curl 範例

```bash
# json 格式
curl -X POST http://192.168.80.224:8002/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-key" \
  -F "file=@audio.wav" -F "model=whisper-1"

# text 格式
curl -X POST http://192.168.80.224:8002/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-key" \
  -F "file=@audio.wav" -F "response_format=text"

# verbose_json（含時間戳記）
curl -X POST http://192.168.80.224:8002/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-key" \
  -F "file=@audio.wav" \
  -F "response_format=verbose_json" \
  -F "timestamp_granularities=segment"
```

### openai SDK 範例

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://192.168.80.224:8002/v1",
    api_key="sk-your-key",
)
with open("audio.wav", "rb") as f:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        language="zh",
    )
print(result.text)
```

### JavaScript 範例

```js
import OpenAI from 'openai'

const client = new OpenAI({
  baseURL: 'http://192.168.80.224:8002/v1',
  apiKey: 'sk-your-key',
  dangerouslyAllowBrowser: true,
})
const result = await client.audio.transcriptions.create({
  model: 'whisper-1',
  file: audioFile,
})
console.log(result.text)
```

---

## 啟動方式

```bash
# 無驗證（本機開發）
bash start_asr.sh

# 單 Key
API_KEY=sk-your-key bash start_asr.sh

# 多 Key
API_KEYS=sk-frontend,sk-mobile,sk-admin bash start_asr.sh

# 完整設定
ASR_MODEL=Qwen/Qwen3-ASR-0.6B \
  ASR_TIMESTAMPS=true \
  API_KEY=sk-your-key \
  bash start_asr.sh

# tmux 背景執行
tmux new-session -d -s asr \
  "API_KEY=sk-your-key bash ~/qwen-api/qwen3asr/start_asr.sh"
```

生成 key：
```bash
python3 -c "import secrets; print('sk-' + secrets.token_hex(16))"
```

---

## 錯誤碼

| 狀態碼 | 說明 |
|--------|------|
| `200` | 成功 |
| `401` | API Key 無效或缺少 |
| `422` | 參數錯誤 |
| `500` | 伺服器內部錯誤 |

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ASR_MODEL` | `Qwen/Qwen3-ASR-1.7B` | 模型名稱 |
| `ASR_TIMESTAMPS` | `false` | 預設啟用時間戳記 |
| `ASR_PORT` | `8002` | 監聽 Port |
| `API_KEY` | `""` | 單一 Key（空 = 不驗證） |
| `API_KEYS` | `""` | 多 Key 逗號分隔（優先於 API_KEY） |

---

## 效能參考（RTX 3060 12GB）

| 項目 | 數據 |
|------|------|
| 模型載入 | ~8s |
| VRAM 占用 | ~4.5 GB |
| 中文短句 | ~0.7s（暖機後） |
| 英文短句 | ~1.9s（暖機後） |
| 批次 4 筆 | ~1.1s/筆 |
