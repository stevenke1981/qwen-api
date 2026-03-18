"""
asr_api_vllm.py — Qwen3-ASR 語音辨識 API Server（vLLM 後端）
Port: 8002

vLLM 版本優勢：
  - 批次吞吐量最高可達 128 並發請求
  - GPU 記憶體利用率優化（PagedAttention）
  - 支援串流推理
  - 適合高並發生產環境

注意：vLLM 後端需要 pip install qwen-asr[vllm]
      且必須在 if __name__ == '__main__': 下啟動（vLLM 要求）

Endpoints:
  POST /transcribe       上傳音訊檔案，回傳轉錄文字
  POST /transcribe/url   透過 URL 轉錄
  POST /transcribe/batch 批次轉錄多個檔案
  GET  /health           健康檢查

呼叫範例：
  curl -X POST http://localhost:8002/transcribe \
    -F "file=@audio.wav" -F "language=Chinese"

  curl -X POST http://localhost:8002/transcribe/batch \
    -F "files=@a.wav" -F "files=@b.wav" \
    -F "languages=Chinese" -F "languages=English"
"""
import sys
import os
import asyncio
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
MODEL = os.environ.get("ASR_MODEL", "Qwen/Qwen3-ASR-1.7B")
GPU_UTIL = float(os.environ.get("ASR_GPU_UTIL", "0.7"))
USE_TIMESTAMPS = os.environ.get("ASR_TIMESTAMPS", "false").lower() == "true"

app = FastAPI(title="Qwen3-ASR API (vLLM)", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model = None

def load_model():
    global model
    from qwen_asr import Qwen3ASRModel
    print(f"[ASR-vLLM] 載入模型：{MODEL}")
    print(f"[ASR-vLLM] GPU 使用率：{GPU_UTIL}  時間戳記：{USE_TIMESTAMPS}")

    kwargs = dict(
        gpu_memory_utilization=GPU_UTIL,
        max_inference_batch_size=128,
        max_new_tokens=4096,
    )
    if USE_TIMESTAMPS:
        kwargs["forced_aligner"] = "Qwen/Qwen3-ForcedAligner-0.6B"
        kwargs["forced_aligner_kwargs"] = dict(
            dtype="bfloat16",
            device_map="cuda:0",
        )

    model = Qwen3ASRModel.LLM(model=MODEL, **kwargs)
    print("[ASR-vLLM] 模型載入完成")

def _transcribe(audio_paths: list, languages: list, timestamps: bool) -> list:
    results = model.transcribe(
        audio=audio_paths,
        language=languages if any(languages) else None,
        return_time_stamps=timestamps and USE_TIMESTAMPS,
    )
    output = []
    for r in results:
        item = {"text": r.text, "language": r.language}
        if timestamps and USE_TIMESTAMPS and r.segments:
            item["segments"] = [
                {"text": s.text, "start": round(s.start_time, 3), "end": round(s.end_time, 3)}
                for s in r.segments
            ]
        output.append(item)
    return output

@app.on_event("startup")
async def startup():
    load_model()

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
        "backend": "vllm",
        "timestamps": USE_TIMESTAMPS,
        "gpu_utilization": GPU_UTIL,
    }

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
):
    suffix = os.path.splitext(file.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        results = _transcribe([tmp_path], [language or ""], timestamps)
        return results[0]
    finally:
        os.unlink(tmp_path)

@app.post("/transcribe/url")
async def transcribe_url(
    url: str = Form(...),
    language: str = Form(default=None),
    timestamps: bool = Form(default=False),
):
    results = _transcribe([url], [language or ""], timestamps)
    return results[0]

@app.post("/transcribe/batch")
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    languages: List[str] = Form(default=[]),
    timestamps: bool = Form(default=False),
):
    """批次轉錄（vLLM 最高可達 128 並發，比單筆效率高）"""
    tmp_paths = []
    try:
        for f in files:
            suffix = os.path.splitext(f.filename)[-1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await f.read())
                tmp_paths.append(tmp.name)

        # 補齊 languages 長度
        langs = list(languages) + [""] * (len(tmp_paths) - len(languages))
        results = _transcribe(tmp_paths, langs, timestamps)
        return {"results": results, "count": len(results)}
    finally:
        for p in tmp_paths:
            if os.path.exists(p):
                os.unlink(p)

def main():
    print(f"[ASR-vLLM] 啟動 API Server — http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
