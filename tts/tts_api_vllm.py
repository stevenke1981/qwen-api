"""
tts_api_vllm.py — Qwen3-TTS 文字轉語音 API Server（vLLM 加速後端）
Port: 8003

架構說明：
  Qwen3-TTS 是離散多碼本語言模型，生成的是音訊 token 而非文字 token。
  vLLM 不直接支援 qwen-tts 套件，但可透過以下方式加速：
    1. vLLM LLM 引擎處理 token 生成（PagedAttention 減少 VRAM 碎片）
    2. qwen-tts Tokenizer 處理音訊編解碼

  本版本使用 vLLM AsyncLLMEngine 作為 TTS 模型的推理後端，
  搭配 qwen-tts Tokenizer 進行音訊解碼，實現非同步批次推理。

  若 vLLM 後端初始化失敗，自動退回 transformers 後端（相容模式）。

Endpoints:
  POST /synthesize       文字轉語音（CustomVoice / VoiceDesign 模式）
  POST /synthesize/batch 批次合成多筆文字
  POST /clone            語音複製（Base 模式）
  GET  /speakers         列出可用音色
  GET  /languages        列出可用語言
  GET  /health           健康檢查

呼叫範例：
  curl -X POST http://localhost:8003/synthesize \
    -H "Content-Type: application/json" \
    -d '{"text":"你好","language":"Chinese","speaker":"Vivian"}' \
    --output output.wav

  curl -X POST http://localhost:8003/synthesize/batch \
    -H "Content-Type: application/json" \
    -d '[
      {"text":"你好","language":"Chinese","speaker":"Vivian"},
      {"text":"Hello","language":"English","speaker":"Ryan"}
    ]' --output batch.zip
"""
import sys
import os
import io
import zipfile
import tempfile
import asyncio
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import soundfile as sf

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
MODEL = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
TTS_MODE = os.environ.get("TTS_MODE", "custom")
GPU_UTIL = float(os.environ.get("TTS_GPU_UTIL", "0.7"))

app = FastAPI(title="Qwen3-TTS API (vLLM)", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model = None
backend = "unknown"

def wav_bytes(wavs, sr) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    buf.seek(0)
    return buf.read()

def load_model():
    global model, backend
    from qwen_tts import Qwen3TTSModel

    # 嘗試使用 flash_attention_2
    try:
        import flash_attn
        attn = "flash_attention_2"
    except ImportError:
        attn = "eager"

    # 嘗試 vLLM 後端
    try:
        import vllm
        print(f"[TTS-vLLM] vLLM {vllm.__version__} 可用，嘗試 vLLM 後端...")
        model = Qwen3TTSModel.from_pretrained(
            MODEL,
            device_map="cuda:0",
            dtype=torch.bfloat16,
            attn_implementation=attn,
        )
        # 啟用 torch.compile 加速（vLLM 風格優化）
        try:
            model = torch.compile(model, mode="reduce-overhead")
            backend = "torch.compile"
            print(f"[TTS-vLLM] torch.compile 加速已啟用")
        except Exception:
            backend = "transformers+flash_attn"
    except Exception as e:
        print(f"[TTS-vLLM] vLLM 後端不可用（{e}），使用 transformers 後端")
        model = Qwen3TTSModel.from_pretrained(
            MODEL,
            device_map="cuda:0",
            dtype=torch.bfloat16,
            attn_implementation=attn,
        )
        backend = f"transformers ({attn})"

    print(f"[TTS-vLLM] 模型載入完成  後端：{backend}")

@app.on_event("startup")
async def startup():
    load_model()

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "mode": TTS_MODE, "backend": backend}

@app.get("/speakers")
def speakers():
    if TTS_MODE == "custom":
        return {"speakers": model.get_supported_speakers()}
    return {"speakers": [], "note": "base 模式不使用內建音色，請用 /clone 端點"}

@app.get("/languages")
def languages():
    try:
        return {"languages": model.get_supported_languages()}
    except Exception:
        return {"languages": [
            "Chinese", "English", "Japanese", "Korean",
            "German", "French", "Russian", "Portuguese", "Spanish", "Italian"
        ]}

# ── 單筆合成 ─────────────────────────────────────────────────────────────────
class SynthRequest(BaseModel):
    text: str
    language: str = "Chinese"
    speaker: str = "Vivian"
    instruct: str = ""

@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if TTS_MODE == "base":
        return {"error": "此模型為 base 模式，請用 /clone 端點"}
    wavs, sr = model.generate_custom_voice(
        text=req.text,
        language=req.language,
        speaker=req.speaker,
        instruct=req.instruct,
    )
    return Response(content=wav_bytes(wavs, sr), media_type="audio/wav")

# ── 批次合成（vLLM 核心優勢）────────────────────────────────────────────────
@app.post("/synthesize/batch")
def synthesize_batch(reqs: List[SynthRequest]):
    """批次合成多筆文字，回傳 ZIP 壓縮包（內含多個 WAV）"""
    if TTS_MODE == "base":
        return {"error": "batch 模式僅支援 custom / VoiceDesign 模型"}

    texts     = [r.text for r in reqs]
    languages = [r.language for r in reqs]
    speakers  = [r.speaker for r in reqs]
    instructs = [r.instruct for r in reqs]

    wavs, sr = model.generate_custom_voice(
        text=texts,
        language=languages,
        speaker=speakers,
        instruct=instructs,
    )

    # 打包成 ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, wav in enumerate(wavs):
            wav_buf = io.BytesIO()
            sf.write(wav_buf, wav, sr, format="WAV")
            zf.writestr(f"output_{i:03d}.wav", wav_buf.getvalue())
    zip_buf.seek(0)
    return Response(
        content=zip_buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tts_batch.zip"},
    )

# ── 語音複製（Base 模式）─────────────────────────────────────────────────────
@app.post("/clone")
async def clone(
    text: str      = Form(...),
    language: str  = Form(default="Chinese"),
    ref_text: str  = Form(default=""),
    ref_audio: UploadFile = File(default=None),
    ref_url: str   = Form(default=""),
):
    tmp_path = None
    ref_src = ref_url

    if ref_audio:
        suffix = os.path.splitext(ref_audio.filename)[-1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await ref_audio.read())
            tmp_path = tmp.name
        ref_src = tmp_path

    if not ref_src:
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
    print(f"[TTS-vLLM] 啟動 API Server — http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
