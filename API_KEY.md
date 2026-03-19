# API Key 認證設定指南

本文件說明如何為 ASR / TTS API 加上 API Key 認證，使其符合商用服務等級。

---

## 認證方式

使用 HTTP Header：

```
X-API-Key: sk-your-secret-key
```

所有需要認證的端點都必須帶上此 Header，否則回傳 `401 Unauthorized`。

---

## 修改 asr_api.py

在 `from fastapi import ...` 那行加入 `Depends, Security`，並新增驗證邏輯：

```python
# 在檔案頂部加入
from fastapi import FastAPI, UploadFile, File, Form, Depends, Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.environ.get("API_KEY", "")          # 空字串 = 不驗證（開發模式）
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_key(key: str = Security(api_key_header)):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

每個需要保護的 endpoint 加入 `Depends(verify_key)`：

```python
@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
    _: None = Depends(verify_key),              # ← 加這行
):
    ...

@app.post("/transcribe/url")
async def transcribe_url(
    url: str = Form(...),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
    _: None = Depends(verify_key),              # ← 加這行
):
    ...
```

`/health` 通常不需要認證，讓監控工具可以直接查詢。

---

## 修改 tts_api.py

同樣方式，在頂部加入驗證邏輯：

```python
from fastapi import FastAPI, UploadFile, File, Form, Depends, Security, HTTPException, Response
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_key(key: str = Security(api_key_header)):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

保護端點：

```python
@app.post("/synthesize")
def synthesize(req: SynthRequest, _: None = Depends(verify_key)):
    ...

@app.post("/clone")
async def clone(
    text: str = Form(...),
    ...,
    _: None = Depends(verify_key),              # ← 加這行
):
    ...
```

---

## 啟動服務時設定 Key

```bash
# ASR
API_KEY=sk-your-secret-key bash start_asr.sh

# TTS
API_KEY=sk-your-secret-key bash start_tts.sh

# tmux 背景執行
tmux new-session -d -s asr "API_KEY=sk-your-secret-key bash ~/qwen-api/qwen3asr/start_asr.sh"
tmux new-session -d -s tts "API_KEY=sk-your-secret-key bash ~/qwen-api/qwen3tts/start_tts.sh"
```

若 `API_KEY` 為空，則不驗證（適合本機開發）。

---

## 前端呼叫範例

### JavaScript

```js
const API_KEY = 'sk-your-secret-key'

// ASR
const form = new FormData()
form.append('file', audioFile)
form.append('language', 'Chinese')

const res = await fetch('http://192.168.80.224:8002/transcribe', {
  method: 'POST',
  headers: { 'X-API-Key': API_KEY },
  body: form,
})
const result = await res.json()

// TTS
const res2 = await fetch('http://192.168.80.224:8003/synthesize', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
  body: JSON.stringify({ text: '你好', language: 'Chinese', speaker: 'Vivian' }),
})
const wav = await res2.blob()
```

### Python

```python
import requests

HEADERS = {'X-API-Key': 'sk-your-secret-key'}

# ASR
with open('audio.wav', 'rb') as f:
    resp = requests.post(
        'http://192.168.80.224:8002/transcribe',
        headers=HEADERS,
        files={'file': f},
        data={'language': 'Chinese'},
    )
print(resp.json())

# TTS
resp = requests.post(
    'http://192.168.80.224:8003/synthesize',
    headers=HEADERS,
    json={'text': '你好', 'language': 'Chinese', 'speaker': 'Vivian'},
)
with open('output.wav', 'wb') as f:
    f.write(resp.content)
```

### curl

```bash
# ASR
curl -X POST http://192.168.80.224:8002/transcribe \
  -H "X-API-Key: sk-your-secret-key" \
  -F "file=@audio.wav" \
  -F "language=Chinese"

# TTS
curl -X POST http://192.168.80.224:8003/synthesize \
  -H "X-API-Key: sk-your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好","language":"Chinese","speaker":"Vivian"}' \
  --output output.wav
```

---

## 多 Key 管理（進階）

若需要多個使用者各自有不同的 key（例如給不同前端或客戶），可改用 set 驗證：

```python
import os

# 環境變數：API_KEYS=key1,key2,key3
VALID_KEYS = set(k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip())

def verify_key(key: str = Security(api_key_header)):
    if VALID_KEYS and key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

啟動：
```bash
API_KEYS=sk-frontend,sk-mobile,sk-admin bash start_asr.sh
```

---

## 安全建議

| 項目 | 建議 |
|------|------|
| Key 格式 | `sk-` 前綴 + 32 位隨機字串，例如 `sk-a3f9b2c1...` |
| 生成指令 | `python3 -c "import secrets; print('sk-' + secrets.token_hex(16))"` |
| 不要硬寫 | 不要把 key 寫進 `.sh` 腳本或前端程式碼 |
| 前端保護 | 若前端是公開頁面，應在後端 proxy 加 key，不要暴露給瀏覽器 |
| HTTPS | 對外服務應加 nginx + Let's Encrypt TLS，避免 key 明文傳輸 |
| 輪換 | key 外洩時直接更換環境變數重啟服務即可 |
