"""
asr_api.py — Qwen3-ASR 語音辨識 API Server
Port: 8002

Endpoints:
  POST /transcribe       上傳音訊檔案，回傳轉錄文字
  GET  /health           健康檢查

用法：
  .venv/bin/python3 asr_api.py [port]

呼叫範例：
  curl -X POST http://localhost:8002/transcribe \
    -F "file=@audio.wav" \
    -F "language=Chinese"

  curl -X POST http://localhost:8002/transcribe \
    -F "file=@audio.wav" \
    -F "timestamps=true"
"""
import sys
import os
import tempfile
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
MODEL = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
USE_TIMESTAMPS = os.environ.get("ASR_TIMESTAMPS", "false").lower() == "true"

app = FastAPI(title="Qwen3-ASR API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model = None

def load_model():
    global model
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
    model = Qwen3ASRModel.from_pretrained(MODEL, **kwargs)
    print(f"[ASR] 模型載入完成，timestamps={'on' if USE_TIMESTAMPS else 'off'}")

@app.on_event("startup")
async def startup():
    load_model()

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "timestamps": USE_TIMESTAMPS}

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=None, description="語言（留空自動偵測）"),
    timestamps: bool = Form(default=False, description="是否回傳時間戳記"),
):
    # 儲存上傳檔案到暫存目錄
    suffix = os.path.splitext(file.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        results = model.transcribe(
            audio=tmp_path,
            language=language if language else None,
            return_time_stamps=timestamps and USE_TIMESTAMPS,
        )
        r = results[0]
        resp = {
            "text": r.text,
            "language": r.language,
        }
        if timestamps and USE_TIMESTAMPS and r.segments:
            resp["segments"] = [
                {"text": s.text, "start": round(s.start_time, 3), "end": round(s.end_time, 3)}
                for s in r.segments
            ]
        return resp
    finally:
        os.unlink(tmp_path)

@app.post("/transcribe/url")
async def transcribe_url(
    url: str = Form(..., description="音訊 URL"),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
):
    results = model.transcribe(
        audio=url,
        language=language if language else None,
        return_time_stamps=timestamps and USE_TIMESTAMPS,
    )
    r = results[0]
    resp = {"text": r.text, "language": r.language}
    if timestamps and USE_TIMESTAMPS and r.segments:
        resp["segments"] = [
            {"text": s.text, "start": round(s.start_time, 3), "end": round(s.end_time, 3)}
            for s in r.segments
        ]
    return resp

if __name__ == "__main__":
    print(f"[ASR] 啟動 API Server — http://0.0.0.0:{PORT}")
    print(f"[ASR] 模型：{MODEL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
