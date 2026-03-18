"""
tts_api.py — Qwen3-TTS 文字轉語音 API Server
Port: 8003

Endpoints:
  POST /synthesize       文字轉語音，回傳 WAV 音訊
  POST /clone            語音複製模式（需提供參考音訊）
  GET  /speakers         列出可用音色
  GET  /languages        列出可用語言
  GET  /health           健康檢查

環境變數：
  TTS_MODEL   模型名稱（預設 Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice）
  TTS_MODE    模式：custom（預設）或 base（語音複製）

用法：
  .venv/bin/python3 tts_api.py [port]

呼叫範例：
  # 內建音色合成
  curl -X POST http://localhost:8003/synthesize \
    -H "Content-Type: application/json" \
    -d '{"text":"你好，歡迎使用語音合成","language":"Chinese","speaker":"Vivian"}' \
    --output output.wav

  # 加情緒指令
  curl -X POST http://localhost:8003/synthesize \
    -H "Content-Type: application/json" \
    -d '{"text":"Hello world","language":"English","speaker":"Ryan","instruct":"Very excited"}' \
    --output output.wav

  # 語音複製（base 模式）
  curl -X POST http://localhost:8003/clone \
    -F "text=你好" \
    -F "language=Chinese" \
    -F "ref_text=OK I got it" \
    -F "ref_audio=@ref.wav" \
    --output output.wav
"""
import sys
import os
import io
import tempfile
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import soundfile as sf
import numpy as np

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
MODEL = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
TTS_MODE = os.environ.get("TTS_MODE", "custom")   # "custom" or "base"

app = FastAPI(title="Qwen3-TTS API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model = None

def wav_bytes(wavs, sr) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    buf.seek(0)
    return buf.read()

def load_model():
    global model
    from qwen_tts import Qwen3TTSModel
    try:
        import flash_attn
        attn = "flash_attention_2"
    except ImportError:
        attn = "eager"
    print(f"[TTS] 載入模型：{MODEL}  模式：{TTS_MODE}")
    model = Qwen3TTSModel.from_pretrained(
        MODEL,
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation=attn,
    )
    print("[TTS] 模型載入完成")

@app.on_event("startup")
async def startup():
    load_model()

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "mode": TTS_MODE}

@app.get("/speakers")
def speakers():
    if TTS_MODE == "custom":
        return {"speakers": model.get_supported_speakers()}
    return {"speakers": [], "note": "base 模式不使用內建音色，請用 /clone 端點"}

@app.get("/languages")
def languages():
    return {"languages": model.get_supported_languages() if TTS_MODE == "custom" else [
        "Chinese", "English", "Japanese", "Korean",
        "German", "French", "Russian", "Portuguese", "Spanish", "Italian"
    ]}

# ── CustomVoice / VoiceDesign 模式 ────────────────────────────────────────────
class SynthRequest(BaseModel):
    text: str
    language: str = "Chinese"
    speaker: str = "Vivian"
    instruct: str = ""

@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if TTS_MODE == "base":
        return {"error": "此模型為 base 模式，請用 /clone 端點，或改用 CustomVoice 模型"}
    wavs, sr = model.generate_custom_voice(
        text=req.text,
        language=req.language,
        speaker=req.speaker,
        instruct=req.instruct,
    )
    return Response(content=wav_bytes(wavs, sr), media_type="audio/wav")

# ── Base 語音複製模式 ──────────────────────────────────────────────────────────
@app.post("/clone")
async def clone(
    text: str      = Form(...,                description="要合成的文字"),
    language: str  = Form(default="Chinese",  description="語言"),
    ref_text: str  = Form(default="",         description="參考音訊的文字內容"),
    ref_audio: UploadFile = File(default=None, description="參考音訊（3 秒 WAV）"),
    ref_url: str   = Form(default="",         description="參考音訊 URL（與 ref_audio 擇一）"),
):
    # 取得參考音訊路徑
    tmp_path = None
    ref_src = ref_url

    if ref_audio:
        suffix = os.path.splitext(ref_audio.filename)[-1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await ref_audio.read())
            tmp_path = tmp.name
        ref_src = tmp_path

    if not ref_src:
        # 使用內建範例音訊
        ref_src = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav"
        ref_text = ref_text or "Okay. Yeah. I resent you. I love you. I respect you."

    try:
        wavs, sr = model.generate_voice_clone(
            text=text,
            language=language,
            ref_audio=ref_src,
            ref_text=ref_text,
        )
        return Response(content=wav_bytes(wavs, sr), media_type="audio/wav")
    finally:
        if tmp_path:
            os.unlink(tmp_path)

if __name__ == "__main__":
    print(f"[TTS] 啟動 API Server — http://0.0.0.0:{PORT}")
    print(f"[TTS] 模型：{MODEL}  模式：{TTS_MODE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
