"""
asr_api.py — Qwen3-ASR 語音辨識 API Server
Port: 8002

認證模式（由環境變數決定）：
  無驗證    API_KEY 與 API_KEYS 均未設定（本機開發）
  單 Key   API_KEY=sk-xxxx
  多 Key   API_KEYS=sk-a,sk-b,sk-c（逗號分隔）

Endpoints:
  GET  /health             健康檢查（不需驗證）
  POST /transcribe         上傳音訊檔案辨識
  POST /transcribe/url     透過 URL 辨識
  POST /v1/audio/transcriptions  OpenAI 相容格式

用法：
  .venv/bin/python3 asr_api.py [port]

呼叫範例（無驗證）：
  curl -X POST http://localhost:8002/transcribe -F "file=@audio.wav"

呼叫範例（有驗證）：
  curl -X POST http://localhost:8002/transcribe \
    -H "X-API-Key: sk-your-key" \
    -F "file=@audio.wav"

OpenAI 相容格式：
  curl -X POST http://localhost:8002/v1/audio/transcriptions \
    -H "Authorization: Bearer sk-your-key" \
    -F "file=@audio.wav" \
    -F "model=whisper-1"
"""
import sys
import os
import tempfile
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, Security, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
MODEL = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
USE_TIMESTAMPS = os.environ.get("ASR_TIMESTAMPS", "false").lower() == "true"

# ── 認證設定 ──────────────────────────────────────────────────────────────────
_raw_key  = os.environ.get("API_KEY", "").strip()
_raw_keys = os.environ.get("API_KEYS", "").strip()

# 多 key 優先；若 API_KEYS 未設但 API_KEY 有值則轉為 set
if _raw_keys:
    VALID_KEYS: set[str] = {k.strip() for k in _raw_keys.split(",") if k.strip()}
elif _raw_key:
    VALID_KEYS = {_raw_key}
else:
    VALID_KEYS = set()   # 空 set → 不驗證

AUTH_ENABLED = bool(VALID_KEYS)

# Header: X-API-Key（自訂格式）
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
# Header: Authorization: Bearer <token>（OpenAI 相容）
_bearer = HTTPBearer(auto_error=False)


def _extract_key(
    header_key: str | None = Security(_api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str | None:
    """從 X-API-Key 或 Authorization Bearer 取出 token。"""
    if header_key:
        return header_key
    if bearer:
        return bearer.credentials
    return None


def verify_key(key: str | None = Depends(_extract_key)) -> None:
    """若啟用驗證，檢查 key 是否合法；/health 不使用此依賴。"""
    if AUTH_ENABLED and key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Qwen3-ASR API",
    version="1.1",
    description="Qwen3-ASR 語音辨識 API，支援單/多 Key 驗證與 OpenAI 相容格式",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

asr_model = None


def load_model():
    global asr_model
    from qwen_asr import Qwen3ASRModel
    print(f"[ASR] 載入模型：{MODEL}")
    kwargs = dict(
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_inference_batch_size=16,
        max_new_tokens=1024,
    )
    if USE_TIMESTAMPS:
        kwargs["forced_aligner"] = "Qwen/Qwen3-ForcedAligner-0.6B"
        kwargs["forced_aligner_kwargs"] = dict(dtype=torch.bfloat16, device_map="cuda:0")
    asr_model = Qwen3ASRModel.from_pretrained(MODEL, **kwargs)
    print(f"[ASR] 模型載入完成，timestamps={'on' if USE_TIMESTAMPS else 'off'}")


@app.on_event("startup")
async def startup():
    load_model()


# ── 健康檢查（不需驗證）──────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
        "timestamps": USE_TIMESTAMPS,
        "auth": "enabled" if AUTH_ENABLED else "disabled",
    }


# ── 內部轉錄邏輯 ──────────────────────────────────────────────────────────────
def _do_transcribe(audio_path: str, language: str | None, timestamps: bool) -> dict:
    results = asr_model.transcribe(
        audio=audio_path,
        language=language if language else None,
        return_time_stamps=timestamps and USE_TIMESTAMPS,
    )
    r = results[0]
    resp = {"text": r.text, "language": r.language}
    if timestamps and USE_TIMESTAMPS and getattr(r, "segments", None):
        resp["segments"] = [
            {"text": s.text, "start": round(s.start_time, 3), "end": round(s.end_time, 3)}
            for s in r.segments
        ]
    return resp


# ── POST /transcribe ──────────────────────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=None, description="語言（留空自動偵測）"),
    timestamps: bool = Form(default=False, description="是否回傳時間戳記"),
    _: None = Depends(verify_key),
):
    suffix = os.path.splitext(file.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return _do_transcribe(tmp_path, language, timestamps)
    finally:
        os.unlink(tmp_path)


# ── POST /transcribe/url ──────────────────────────────────────────────────────
@app.post("/transcribe/url")
async def transcribe_url(
    url: str = Form(..., description="音訊 URL"),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
    _: None = Depends(verify_key),
):
    return _do_transcribe(url, language, timestamps)


# ── POST /v1/audio/transcriptions（OpenAI Whisper 相容）──────────────────────
@app.post("/v1/audio/transcriptions")
async def openai_transcriptions(
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: str = Form(default=None, description="ISO-639-1 語言代碼或全名"),
    response_format: str = Form(default="json", description="json | text | verbose_json"),
    timestamp_granularities: str = Form(default="", description="word / segment（逗號分隔）"),
    _: None = Depends(verify_key),
):
    """
    OpenAI /v1/audio/transcriptions 相容端點。
    可直接用 openai Python SDK 或任何支援 Whisper API 的工具呼叫。
    """
    want_ts = "word" in timestamp_granularities or "segment" in timestamp_granularities
    suffix = os.path.splitext(file.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = _do_transcribe(tmp_path, language, want_ts)
    finally:
        os.unlink(tmp_path)

    if response_format == "text":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(result["text"])

    if response_format == "verbose_json":
        return {
            "task": "transcribe",
            "language": result.get("language", ""),
            "text": result["text"],
            "segments": result.get("segments", []),
        }

    # default: json
    return {"text": result["text"]}


if __name__ == "__main__":
    mode = f"認證：{'啟用 (' + str(len(VALID_KEYS)) + ' key)' if AUTH_ENABLED else '停用（無 API_KEY）'}"
    print(f"[ASR] 啟動 API Server — http://0.0.0.0:{PORT}")
    print(f"[ASR] 模型：{MODEL}")
    print(f"[ASR] {mode}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
