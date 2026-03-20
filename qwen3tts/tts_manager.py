"""
tts_manager.py — Qwen3-TTS 統一管理器（OpenAI 相容）
Port: 8090（預設）

認證（與 asr_api.py 相同模式）：
  無驗證    API_KEY / API_KEYS 均未設定
  單 Key   API_KEY=sk-xxxx
  多 Key   API_KEYS=sk-a,sk-b,sk-c

主要端點：
  POST /v1/audio/speech          OpenAI 相容，帶 model 欄位自動切換
  GET  /v1/models                可用模型清單（OpenAI 相容）
  POST /synthesize               語音合成（custom / design）
  POST /clone                    語音複製（base）
  GET  /speakers                 目前模型音色清單
  GET  /languages                目前模型語言清單
  GET  /health                   健康檢查（不需驗證）

管理端點（不需驗證）：
  GET  /                         管理 UI
  GET  /api/models               所有模型 + 狀態
  GET  /api/status               目前模型 + VRAM
  POST /api/models/{id}/activate 手動切換模型

呼叫範例：
  # OpenAI 相容
  curl -X POST http://localhost:8090/v1/audio/speech \\
    -H "Authorization: Bearer sk-your-key" \\
    -H "Content-Type: application/json" \\
    -d '{"model":"tts-1.7b-custom","input":"你好","voice":"Vivian","language":"Chinese"}' \\
    --output out.wav

  # 語音複製（base）
  curl -X POST http://localhost:8090/v1/audio/speech \\
    -H "Authorization: Bearer sk-your-key" \\
    -H "Content-Type: application/json" \\
    -d '{"model":"tts-1.7b-base","input":"你好","language":"Chinese","ref_audio_url":"https://...","ref_text":"..."}' \\
    --output out.wav

環境變數：
  API_KEY           單一 API Key
  API_KEYS          多 API Key（逗號分隔）
  TTS_DEFAULT_MODEL 啟動預載模型 ID（預設 tts-1.7b-custom）
"""
import sys, os, io, gc, asyncio, tempfile, time, threading
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, Security, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import Optional

try:
    import soundfile as sf
except ImportError:
    sf = None

PORT        = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
DEFAULT_MODEL = os.environ.get("TTS_DEFAULT_MODEL", "tts-1.7b-custom")

# ── 模型清單 ───────────────────────────────────────────────────────────────────
MODELS = [
    {"id": "tts-0.6b-base",   "name": "TTS-0.6B-Base",
     "repo": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",         "type": "base",   "vram": 2,
     "desc": "輕量語音複製，提供 3 秒參考音訊複製任意音色"},
    {"id": "tts-1.7b-base",   "name": "TTS-1.7B-Base",
     "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",         "type": "base",   "vram": 4,
     "desc": "高品質語音複製，提供 3 秒參考音訊複製任意音色"},
    {"id": "tts-0.6b-custom", "name": "TTS-0.6B-CustomVoice",
     "repo": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",  "type": "custom", "vram": 2,
     "desc": "輕量版，9 種內建音色 + 自然語言情緒控制"},
    {"id": "tts-1.7b-custom", "name": "TTS-1.7B-CustomVoice",
     "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",  "type": "custom", "vram": 4,
     "desc": "高品質，9 種內建音色 + 自然語言情緒控制 ✅"},
    {"id": "tts-1.7b-design", "name": "TTS-1.7B-VoiceDesign",
     "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",  "type": "design", "vram": 4,
     "desc": "用自然語言文字描述設計專屬音色"},
]
MODEL_MAP = {m["id"]: m for m in MODELS}

# ── 認證 ───────────────────────────────────────────────────────────────────────
_raw_key  = os.environ.get("API_KEY",  "").strip()
_raw_keys = os.environ.get("API_KEYS", "").strip()
if _raw_keys:
    VALID_KEYS: set[str] = {k.strip() for k in _raw_keys.split(",") if k.strip()}
elif _raw_key:
    VALID_KEYS = {_raw_key}
else:
    VALID_KEYS = set()
AUTH_ENABLED = bool(VALID_KEYS)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer         = HTTPBearer(auto_error=False)

def _extract_key(
    hk: str | None = Security(_api_key_header),
    br: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> str | None:
    return hk or (br.credentials if br else None)

def verify_key(key: str | None = Depends(_extract_key)) -> None:
    if AUTH_ENABLED and key not in VALID_KEYS:
        raise HTTPException(401, "Invalid or missing API Key")

# ── 全域狀態 ───────────────────────────────────────────────────────────────────
state: dict = {
    "model":      None,
    "active_id":  None,
    "loading":    False,
    "loading_id": None,
    "error":      None,
    "loaded_at":  None,
}
_load_lock   = threading.Lock()   # 同步鎖，防止並發切換
_async_lock  = asyncio.Lock()     # 非同步層

# ── VRAM ───────────────────────────────────────────────────────────────────────
def vram_info() -> dict:
    if not torch.cuda.is_available():
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0}
    prop  = torch.cuda.get_device_properties(0)
    total = prop.total_memory
    alloc = torch.cuda.memory_allocated(0)
    return {
        "total_gb": round(total / 1024**3, 1),
        "used_gb":  round(alloc  / 1024**3, 1),
        "free_gb":  round((total - alloc) / 1024**3, 1),
        "device":   prop.name,
    }

# ── 模型操作 ───────────────────────────────────────────────────────────────────
def _wav_bytes(wavs, sr) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, wavs[0], sr, format="WAV")
    buf.seek(0)
    return buf.read()

def _unload():
    if state["model"] is not None:
        del state["model"]
        state["model"] = None
        gc.collect()
        torch.cuda.empty_cache()
        print("[MGR] 模型已卸載，VRAM 已清空")

def _load_sync(model_id: str):
    """同步載入，在 executor 中執行。"""
    with _load_lock:
        if state["active_id"] == model_id and state["model"] is not None:
            return   # 已是目標模型，略過
        from qwen_tts import Qwen3TTSModel
        meta = MODEL_MAP[model_id]
        state["loading"]    = True
        state["loading_id"] = model_id
        state["error"]      = None
        try:
            _unload()
            try:
                import flash_attn
                attn = "flash_attention_2"
            except ImportError:
                attn = "eager"
            print(f"[MGR] 載入 {meta['name']} ...")
            state["model"] = Qwen3TTSModel.from_pretrained(
                meta["repo"], device_map="cuda:0",
                dtype=torch.bfloat16, attn_implementation=attn,
            )
            state["active_id"] = model_id
            state["loaded_at"] = time.time()
            print(f"[MGR] 載入完成：{meta['name']}")
        except Exception as e:
            state["error"] = str(e)
            print(f"[MGR] 載入失敗：{e}")
            raise
        finally:
            state["loading"]    = False
            state["loading_id"] = None

async def ensure_model(model_id: str):
    """確保目標模型已載入（若需切換則等待完成）。"""
    if state["active_id"] == model_id and state["model"] is not None:
        return
    async with _async_lock:
        if state["active_id"] == model_id and state["model"] is not None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_sync, model_id)
        if state["error"]:
            raise HTTPException(500, f"模型載入失敗：{state['error']}")

# ── FastAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Qwen3-TTS Manager",
    version="2.0",
    description="統一 TTS API，支援 5 種模型熱切換與 OpenAI 相容格式",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(
        asyncio.get_event_loop().run_in_executor(None, _load_sync, DEFAULT_MODEL)
    )

# ── OpenAI 相容端點 ────────────────────────────────────────────────────────────
class SpeechRequest(BaseModel):
    model:         str            = "tts-1.7b-custom"
    input:         str            # 要合成的文字
    voice:         str            = "Vivian"
    language:      str            = "Chinese"
    instruct:      str            = ""
    # base 模式額外欄位
    ref_audio_url: Optional[str]  = None
    ref_text:      Optional[str]  = None
    response_format: str          = "wav"

@app.post("/v1/audio/speech", dependencies=[Depends(verify_key)])
async def v1_speech(req: SpeechRequest):
    if req.model not in MODEL_MAP:
        raise HTTPException(400, f"未知模型：{req.model}。可用：{list(MODEL_MAP)}")
    await ensure_model(req.model)
    model_type = MODEL_MAP[req.model]["type"]
    m = state["model"]
    if model_type == "base":
        ref_src  = req.ref_audio_url or "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav"
        ref_text = req.ref_text      or "Okay. Yeah. I resent you. I love you. I respect you."
        wavs, sr = m.generate_voice_clone(
            text=req.input, language=req.language,
            ref_audio=ref_src, ref_text=ref_text,
        )
    else:
        wavs, sr = m.generate_custom_voice(
            text=req.input, language=req.language,
            speaker=req.voice, instruct=req.instruct,
        )
    return Response(content=_wav_bytes(wavs, sr), media_type="audio/wav")

@app.get("/v1/models", dependencies=[Depends(verify_key)])
def v1_models():
    return {
        "object": "list",
        "data": [
            {"id": m["id"], "object": "model", "type": m["type"],
             "vram_gb": m["vram"], "description": m["desc"]}
            for m in MODELS
        ],
    }

# ── 舊版端點（向後相容）────────────────────────────────────────────────────────
class SynthRequest(BaseModel):
    text: str;  language: str = "Chinese"
    speaker: str = "Vivian";  instruct: str = ""

@app.post("/synthesize", dependencies=[Depends(verify_key)])
async def synthesize(req: SynthRequest):
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    if MODEL_MAP.get(state["active_id"], {}).get("type") == "base":
        raise HTTPException(400, "當前為 base 模式，請使用 /clone 端點")
    wavs, sr = state["model"].generate_custom_voice(
        text=req.text, language=req.language,
        speaker=req.speaker, instruct=req.instruct,
    )
    return Response(content=_wav_bytes(wavs, sr), media_type="audio/wav")

@app.post("/clone", dependencies=[Depends(verify_key)])
async def clone(
    text:      str        = Form(...),
    language:  str        = Form(default="Chinese"),
    ref_text:  str        = Form(default=""),
    ref_audio: UploadFile = File(default=None),
    ref_url:   str        = Form(default=""),
):
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    tmp_path, ref_src = None, ref_url
    if ref_audio:
        suffix = os.path.splitext(ref_audio.filename)[-1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await ref_audio.read())
            tmp_path = tmp.name
        ref_src = tmp_path
    if not ref_src:
        ref_src  = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone.wav"
        ref_text = ref_text or "Okay. Yeah. I resent you. I love you. I respect you."
    try:
        wavs, sr = state["model"].generate_voice_clone(
            text=text, language=language, ref_audio=ref_src, ref_text=ref_text,
        )
        return Response(content=_wav_bytes(wavs, sr), media_type="audio/wav")
    finally:
        if tmp_path:
            os.unlink(tmp_path)

# ── 工具端點 ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "active_model": state["active_id"],
            "loading": state["loading"], "auth": AUTH_ENABLED}

@app.get("/speakers", dependencies=[Depends(verify_key)])
def speakers():
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    if MODEL_MAP.get(state["active_id"], {}).get("type") == "base":
        return {"speakers": [], "note": "base 模式請使用 /clone 端點"}
    return {"speakers": state["model"].get_supported_speakers()}

@app.get("/languages", dependencies=[Depends(verify_key)])
def languages():
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    if hasattr(state["model"], "get_supported_languages"):
        return {"languages": state["model"].get_supported_languages()}
    return {"languages": ["Chinese","English","Japanese","Korean","German",
                          "French","Russian","Portuguese","Spanish","Italian"]}

# ── 管理 API（不需驗證）────────────────────────────────────────────────────────
@app.get("/api/models")
def api_models():
    return [
        {**m, "active": m["id"] == state["active_id"],
         "loading": m["id"] == state["loading_id"]}
        for m in MODELS
    ]

@app.get("/api/status")
def api_status():
    active = MODEL_MAP.get(state["active_id"]) if state["active_id"] else None
    return {
        "active_id":   state["active_id"],
        "active_name": active["name"] if active else None,
        "active_type": active["type"] if active else None,
        "loading":     state["loading"],
        "loading_id":  state["loading_id"],
        "error":       state["error"],
        "auth_enabled": AUTH_ENABLED,
        "vram":        vram_info(),
    }

@app.post("/api/models/{model_id}/activate")
async def api_activate(model_id: str):
    if model_id not in MODEL_MAP:
        raise HTTPException(404, f"未知模型 ID：{model_id}")
    if state["loading"]:
        raise HTTPException(409, "另一個模型正在載入中，請稍候")
    if state["active_id"] == model_id and state["model"] is not None:
        return {"status": "already_active", "model_id": model_id}
    loop = asyncio.get_event_loop()
    asyncio.create_task(loop.run_in_executor(None, _load_sync, model_id))
    return {"status": "loading", "model_id": model_id}

# ── 管理 UI ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def ui():
    return HTMLResponse(content=MANAGER_UI)

MANAGER_UI = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen3-TTS 模型管理</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh;padding:24px}
  h1{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px}
  .sub{color:#64748b;font-size:.85rem;margin-bottom:24px}
  code{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:.82rem}

  .info-bar{background:#1e293b;border-radius:8px;padding:14px 18px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
  .info-item{font-size:.82rem;color:#94a3b8}
  .info-item b{color:#e2e8f0}

  .vram-bar{background:#1e293b;border-radius:8px;padding:14px 18px;margin-bottom:24px;display:flex;align-items:center;gap:16px}
  .vram-label{color:#94a3b8;font-size:.8rem;white-space:nowrap}
  .bar-wrap{flex:1;background:#334155;border-radius:4px;height:8px;overflow:hidden}
  .bar-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6);transition:width .5s}
  .vram-nums{font-size:.8rem;color:#94a3b8;white-space:nowrap}

  .status-chip{display:inline-flex;align-items:center;gap:6px;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:6px 14px;font-size:.8rem;margin-bottom:24px}
  .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0}
  .dot.loading{background:#f59e0b;animation:pulse 1s infinite}
  .dot.err{background:#ef4444}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:16px;margin-bottom:32px}
  .card{background:#1e293b;border:2px solid #334155;border-radius:12px;padding:18px;transition:border-color .2s}
  .card.active{border-color:#3b82f6;background:#172340}
  .card.loading-card{border-color:#f59e0b}
  .card-name{font-weight:600;font-size:.95rem;color:#f1f5f9;margin-bottom:6px}
  .badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
  .badge{font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:600}
  .badge-base{background:#1e40af;color:#93c5fd}
  .badge-custom{background:#14532d;color:#86efac}
  .badge-design{background:#4c1d95;color:#c4b5fd}
  .badge-active{background:#166534;color:#4ade80}
  .badge-loading{background:#78350f;color:#fcd34d}
  .vram-req{font-size:.75rem;color:#64748b;margin-bottom:8px}
  .card-desc{font-size:.82rem;color:#94a3b8;line-height:1.5;margin-bottom:14px}
  .btn{width:100%;padding:8px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:opacity .2s}
  .btn-activate{background:#3b82f6;color:#fff}.btn-activate:hover{opacity:.85}
  .btn-activate:disabled{background:#334155;color:#64748b;cursor:not-allowed}
  .btn-active{background:#166534;color:#4ade80;cursor:default}
  .btn-loading{background:#78350f;color:#fcd34d;cursor:wait}

  .panel{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px}
  .panel h2{font-size:1rem;font-weight:600;margin-bottom:16px;color:#f1f5f9}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
  label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:4px}
  input,select,textarea{width:100%;background:#0f1117;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px 10px;font-size:.9rem}
  textarea{resize:vertical;min-height:80px}
  .btn-synth{background:#8b5cf6;color:#fff;border:none;border-radius:8px;padding:10px 20px;cursor:pointer;font-size:.9rem;font-weight:600}
  .btn-synth:hover{opacity:.85}.btn-synth:disabled{opacity:.4;cursor:not-allowed}
  audio{width:100%;margin-top:12px;border-radius:6px}
  .err-msg{color:#f87171;font-size:.82rem;margin-top:8px}
  .note{font-size:.78rem;color:#475569;margin-top:8px}
</style>
</head>
<body>
<h1>Qwen3-TTS 模型管理</h1>
<p class="sub">Frontend 整合：設定 API URL + API Key，請求帶 <code>model</code> 欄位自動切換</p>

<div class="info-bar" id="info-bar">
  <div class="info-item">API URL <b id="info-url">—</b></div>
  <div class="info-item">認證 <b id="info-auth">—</b></div>
  <div class="info-item">端點 <code>POST /v1/audio/speech</code></div>
  <div class="info-item">文件 <a href="/docs" style="color:#60a5fa">/docs</a></div>
</div>

<div class="vram-bar">
  <span class="vram-label">GPU VRAM</span>
  <div class="bar-wrap"><div class="bar-fill" id="vram-fill" style="width:0%"></div></div>
  <span class="vram-nums" id="vram-nums">—</span>
</div>

<div class="status-chip">
  <span class="dot" id="status-dot"></span>
  <span id="status-text">初始化中...</span>
</div>

<div class="grid" id="model-grid"></div>

<div class="panel">
  <h2>測試合成（對應 POST /v1/audio/speech）</h2>
  <div style="margin-bottom:12px">
    <label>文字</label>
    <textarea id="t-text">你好，這是 Qwen3-TTS 語音合成測試。</textarea>
  </div>
  <div class="row">
    <div>
      <label>語言</label>
      <select id="t-lang">
        <option>Chinese</option><option>English</option><option>Japanese</option>
        <option>Korean</option><option>German</option><option>French</option>
        <option>Russian</option><option>Portuguese</option><option>Spanish</option><option>Italian</option>
      </select>
    </div>
    <div>
      <label>音色（custom / design 模式）</label>
      <select id="t-speaker">
        <option>Vivian</option><option>Serena</option><option>Uncle_Fu</option>
        <option>Dylan</option><option>Eric</option><option>Ryan</option>
        <option>Aiden</option><option>Ono_Anna</option><option>Sohee</option>
      </select>
    </div>
  </div>
  <div style="margin-bottom:12px">
    <label>情緒指令（選填）</label>
    <input id="t-instruct" type="text" placeholder="如：用特別開心的語氣說">
  </div>
  <button class="btn-synth" id="t-btn" onclick="synthesize()">▶ 合成語音</button>
  <div class="err-msg" id="t-err"></div>
  <audio id="t-audio" controls style="display:none"></audio>
  <p class="note">此測試使用當前啟用的模型。base 模式請直接呼叫 <code>POST /v1/audio/speech</code>（帶 ref_audio_url）。</p>
</div>

<script>
async function fetchStatus() {
  try {
    const s = await (await fetch('/api/status')).json();
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    if (s.loading) {
      dot.className = 'dot loading';
      txt.textContent = `載入中：${s.loading_id}...`;
    } else if (s.error) {
      dot.className = 'dot err';
      txt.textContent = `錯誤：${s.error}`;
    } else if (s.active_name) {
      dot.className = 'dot';
      txt.textContent = `啟用中：${s.active_name}`;
    } else {
      dot.className = 'dot err';
      txt.textContent = '尚未載入模型';
    }
    if (s.vram && s.vram.total_gb > 0) {
      const pct = (s.vram.used_gb / s.vram.total_gb * 100).toFixed(0);
      document.getElementById('vram-fill').style.width = pct + '%';
      document.getElementById('vram-nums').textContent =
        `${s.vram.used_gb} / ${s.vram.total_gb} GB (${pct}%)  ${s.vram.device || ''}`;
    }
    document.getElementById('info-url').textContent = location.origin;
    document.getElementById('info-auth').textContent = s.auth_enabled ? '已啟用（API Key）' : '未啟用';
    return s;
  } catch(e) { return null; }
}

async function renderGrid() {
  const [models] = await Promise.all([
    fetch('/api/models').then(r=>r.json()),
    fetchStatus(),
  ]);
  const grid = document.getElementById('model-grid');
  const typeColor = t => t==='base'?'badge-base':t==='custom'?'badge-custom':'badge-design';
  grid.innerHTML = models.map(m => {
    let btn = m.active
      ? `<button class="btn btn-active" disabled>✅ 啟用中</button>`
      : m.loading
        ? `<button class="btn btn-loading" disabled>⏳ 載入中...</button>`
        : `<button class="btn btn-activate" onclick="activate('${m.id}')">啟用</button>`;
    return `<div class="card ${m.active?'active':''} ${m.loading?'loading-card':''}">
      <div class="card-name">${m.name}</div>
      <div class="badges">
        <span class="badge ${typeColor(m.type)}">${m.type}</span>
        ${m.active  ? '<span class="badge badge-active">啟用中</span>' : ''}
        ${m.loading ? '<span class="badge badge-loading">載入中</span>' : ''}
      </div>
      <div class="vram-req">VRAM ≥ ${m.vram} GB</div>
      <div class="card-desc">${m.desc}</div>${btn}</div>`;
  }).join('');
}

async function activate(id) {
  await fetch(`/api/models/${id}/activate`, {method:'POST'});
  renderGrid();
}

async function synthesize() {
  const btn = document.getElementById('t-btn');
  const err = document.getElementById('t-err');
  const aud = document.getElementById('t-audio');
  err.textContent = ''; btn.disabled = true; btn.textContent = '合成中...';
  try {
    const r = await fetch('/v1/audio/speech', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        model: (await fetch('/api/status').then(r=>r.json())).active_id || 'tts-1.7b-custom',
        input: document.getElementById('t-text').value,
        language: document.getElementById('t-lang').value,
        voice: document.getElementById('t-speaker').value,
        instruct: document.getElementById('t-instruct').value,
      }),
    });
    if (!r.ok) { err.textContent = (await r.json()).detail || '合成失敗'; return; }
    aud.src = URL.createObjectURL(await r.blob());
    aud.style.display = 'block'; aud.play();
  } catch(e) { err.textContent = e.message; }
  finally { btn.disabled = false; btn.textContent = '▶ 合成語音'; }
}

renderGrid();
setInterval(renderGrid, 2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"[MGR] Qwen3-TTS Manager v2  — http://0.0.0.0:{PORT}/")
    print(f"[MGR] 預載模型：{DEFAULT_MODEL}")
    print(f"[MGR] 認證：{'已啟用' if AUTH_ENABLED else '未啟用（設定 API_KEY=sk-xxx 啟用）'}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
