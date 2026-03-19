# Qwen3-TTS API 文件

**Base URL:** `http://192.168.80.224:8003`

---

## 端點總覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/health` | 健康檢查 |
| `GET` | `/speakers` | 列出可用音色 |
| `GET` | `/languages` | 列出可用語言 |
| `POST` | `/synthesize` | 文字轉語音（CustomVoice 模式） |
| `POST` | `/clone` | 語音複製（Base 模式） |

---

## GET /health

**回傳範例：**
```json
{
  "status": "ok",
  "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
  "mode": "custom"
}
```

---

## GET /speakers

列出當前模型支援的音色。

**回傳範例（CustomVoice 模式）：**
```json
{
  "speakers": ["Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee"]
}
```

### 音色說明

| 音色 | 語言 | 特色 |
|------|------|------|
| `Vivian` | 中文 | 明亮略帶個性的年輕女聲 |
| `Serena` | 中文 | 溫柔親切的年輕女聲 |
| `Uncle_Fu` | 中文 | 成熟男聲，低沉醇厚 |
| `Dylan` | 中文 | 北京青年男聲，清晰 |
| `Eric` | 中文 | 成都男聲，帶磁性 |
| `Ryan` | 英文 | 活力男聲，節奏感強 |
| `Aiden` | 英文 | 陽光美式男聲，清澈 |
| `Ono_Anna` | 日文 | 活潑日本女聲，輕盈 |
| `Sohee` | 韓文 | 溫暖韓國女聲，情感豐富 |

---

## GET /languages

**回傳範例：**
```json
{
  "languages": ["Chinese", "English", "Japanese", "Korean", "German", "French", "Russian", "Portuguese", "Spanish", "Italian"]
}
```

---

## POST /synthesize

文字轉語音，使用內建音色。

**Content-Type:** `application/json`

**回傳：** `audio/wav` 二進位

### 參數

| 欄位 | 類型 | 必填 | 預設 | 說明 |
|------|------|------|------|------|
| `text` | string | ✅ | — | 要合成的文字 |
| `language` | string | ❌ | `"Chinese"` | 語言 |
| `speaker` | string | ❌ | `"Vivian"` | 音色名稱 |
| `instruct` | string | ❌ | `""` | 情緒 / 風格指令 |

### instruct 指令範例

```
很開心地說  /  用悲傷的語氣  /  輕聲細語
Very excited tone  /  Speak slowly and calmly
```

### curl 範例

```bash
# 基本合成
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，歡迎使用語音合成","language":"Chinese","speaker":"Vivian"}' \
  --output output.wav

# 加情緒指令
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","language":"English","speaker":"Ryan","instruct":"Very excited tone"}' \
  --output output.wav

# 英文男聲
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Welcome to our service","language":"English","speaker":"Aiden"}' \
  --output output.wav
```

### JavaScript 範例

```js
async function synthesize(text, language = 'Chinese', speaker = 'Vivian', instruct = '') {
  const res = await fetch('http://192.168.80.224:8003/synthesize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language, speaker, instruct }),
  })
  if (!res.ok) throw new Error(await res.text())

  const blob = await res.blob()           // audio/wav
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.play()
}
```

### Python 範例

```python
import requests

resp = requests.post(
    'http://192.168.80.224:8003/synthesize',
    json={
        'text': '你好，歡迎使用語音合成',
        'language': 'Chinese',
        'speaker': 'Vivian',
        'instruct': '',
    }
)
with open('output.wav', 'wb') as f:
    f.write(resp.content)
```

---

## POST /clone

語音複製（Base 模式），用參考音訊複製聲音特徵。

**Content-Type:** `multipart/form-data`

**回傳：** `audio/wav` 二進位

### 參數

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `text` | string | ✅ | 要合成的文字 |
| `language` | string | ❌ | 語言（預設 `Chinese`） |
| `ref_text` | string | ❌ | 參考音訊的文字內容（提升品質） |
| `ref_audio` | binary | ❌ | 參考音訊檔案（3 秒 WAV，與 ref_url 擇一） |
| `ref_url` | string | ❌ | 參考音訊 URL（與 ref_audio 擇一） |

> 不提供 ref_audio / ref_url 時使用內建範例音訊。

### curl 範例

```bash
# 上傳參考音訊
curl -X POST http://192.168.80.224:8003/clone \
  -F "text=你好，這是複製的聲音" \
  -F "language=Chinese" \
  -F "ref_text=OK I got it" \
  -F "ref_audio=@ref.wav" \
  --output cloned.wav

# 使用參考音訊 URL
curl -X POST http://192.168.80.224:8003/clone \
  -F "text=Hello world" \
  -F "language=English" \
  -F "ref_url=https://example.com/ref.wav" \
  --output cloned.wav
```

### JavaScript 範例

```js
async function cloneVoice(text, refAudioFile, refText = '', language = 'Chinese') {
  const form = new FormData()
  form.append('text', text)
  form.append('language', language)
  form.append('ref_text', refText)
  form.append('ref_audio', refAudioFile)

  const res = await fetch('http://192.168.80.224:8003/clone', {
    method: 'POST',
    body: form,
  })
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.play()
}
```

---

## 錯誤回傳

| 狀態碼 | 說明 |
|--------|------|
| `200` | 成功，回傳 WAV |
| `422` | 參數錯誤 |
| `500` | 伺服器內部錯誤 |

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `TTS_MODEL` | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | 模型名稱 |
| `TTS_MODE` | `custom` | 模式：`custom` 或 `base` |
| `TTS_PORT` | `8003` | 監聽 Port |

```bash
# 切換為 Base 語音複製模式
TTS_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base TTS_MODE=base bash start_tts.sh

# 切換為 0.6B 輕量模型
TTS_MODEL=Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice bash start_tts.sh
```

---

## 效能參考（RTX 3060 12GB）

| 項目 | 數據 |
|------|------|
| 模型載入 | ~10s |
| VRAM 占用 | ~4 GB |
| 端到端延遲 | ~97ms（串流模式） |
| 同時跑 ASR+TTS | ~8.5 GB VRAM |
