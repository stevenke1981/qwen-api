# Qwen3-ASR API 文件

**Base URL:** `http://192.168.80.224:8002`

---

## 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `POST` | `/transcribe` | 上傳音訊檔案辨識 |
| `POST` | `/transcribe/url` | 透過 URL 辨識 |

---

## GET /health

確認服務狀態與載入的模型。

**回傳範例：**
```json
{
  "status": "ok",
  "model": "Qwen/Qwen3-ASR-1.7B",
  "timestamps": false
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
| `timestamps` | bool | ❌ | `true` 啟用時間戳記（需安裝 ForcedAligner） |

### 支援語言值

```
Chinese  English  Japanese  Korean  German  French
Spanish  Portuguese  Russian  Italian  Arabic  Hindi
Indonesian  Vietnamese  Thai  Turkish  Malay  Dutch
Swedish  Danish  Finnish  Polish  Czech  Filipino
Persian  Greek  Hungarian  Macedonian  Romanian
Cantonese（粵語）
```

### 回傳格式

**一般轉錄：**
```json
{
  "text": "甚至出現交易幾乎停滯的情況。",
  "language": "Chinese"
}
```

**含時間戳記（timestamps=true）：**
```json
{
  "text": "甚至出現交易幾乎停滯的情況。",
  "language": "Chinese",
  "segments": [
    { "text": "甚至", "start": 0.12, "end": 0.48 },
    { "text": "出現", "start": 0.50, "end": 0.86 }
  ]
}
```

### curl 範例

```bash
# 自動偵測語言
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
```

### JavaScript 範例

```js
async function transcribe(audioFile, language = '') {
  const form = new FormData()
  form.append('file', audioFile)
  if (language) form.append('language', language)

  const res = await fetch('http://192.168.80.224:8002/transcribe', {
    method: 'POST',
    body: form,
  })
  return await res.json()
  // { text: '...', language: 'Chinese' }
}
```

### Python 範例

```python
import requests

with open('audio.wav', 'rb') as f:
    resp = requests.post(
        'http://192.168.80.224:8002/transcribe',
        files={'file': f},
        data={'language': 'Chinese'},
    )
print(resp.json())
# {'text': '...', 'language': 'Chinese'}
```

---

## POST /transcribe/url

透過音訊 URL 進行辨識，不需上傳檔案。

**Content-Type:** `multipart/form-data`

### 參數

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `url` | string | ✅ | 音訊檔案的公開 URL |
| `language` | string | ❌ | 語言（留空自動偵測） |
| `timestamps` | bool | ❌ | 啟用時間戳記 |

### curl 範例

```bash
curl -X POST http://192.168.80.224:8002/transcribe/url \
  -F "url=https://example.com/audio.wav" \
  -F "language=English"
```

### JavaScript 範例

```js
async function transcribeUrl(url, language = '') {
  const form = new FormData()
  form.append('url', url)
  if (language) form.append('language', language)

  const res = await fetch('http://192.168.80.224:8002/transcribe/url', {
    method: 'POST',
    body: form,
  })
  return await res.json()
}
```

---

## 錯誤回傳

| 狀態碼 | 說明 |
|--------|------|
| `200` | 成功 |
| `422` | 參數錯誤（缺少 file 或格式錯誤） |
| `500` | 伺服器內部錯誤 |

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ASR_MODEL` | `Qwen/Qwen3-ASR-1.7B` | 模型名稱 |
| `ASR_TIMESTAMPS` | `false` | 預設啟用時間戳記 |
| `ASR_PORT` | `8002` | 監聽 Port |

```bash
# 切換為 0.6B 並啟用時間戳記
ASR_MODEL=Qwen/Qwen3-ASR-0.6B ASR_TIMESTAMPS=true bash start_asr.sh
```

---

## 效能參考（RTX 3060 12GB）

| 項目 | 數據 |
|------|------|
| 模型載入 | ~8s |
| VRAM 占用 | ~4.5 GB |
| 中文短句 | ~0.7s（暖機後） |
| 英文短句 | ~1.9s（暖機後） |
| 批次 4 筆 | ~1.1s/筆 |
