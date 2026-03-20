"""
tts_manager.py — Qwen3-TTS 多模型管理器
Port: 8090（預設）

功能：
  - 管理 5 種 Qwen3-TTS 模型，一次只載入一個（受 VRAM 限制）
  - 熱切換：自動卸載當前模型、清空 VRAM、載入新模型
  - 統一 API 端點，frontend 不需感知底層模型
  - 內建管理 UI（瀏覽器直接操作）

API:
  GET  /                         管理 UI
  GET  /api/models               所有模型清單 + 狀態
  GET  /api/status               目前載入模型 + VRAM
  POST /api/models/{id}/activate 切換模型（背景執行，可輪詢 /api/status）
  POST /synthesize               語音合成（custom / design 模式）
  POST /clone                    語音複製（base 模式）
  GET  /speakers                 目前模型音色清單
  GET  /languages                目前模型語言清單
  GET  /health                   健康檢查

用法：
  ../.venv/bin/python3 tts_manager.py [port]
  或 bash start_tts_manager.sh
"""
import sys, os, io, gc, asyncio, tempfile, time
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel

try:
    import soundfile as sf
except ImportError:
    sf = None

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
DEFAULT_MODEL = os.environ.get("TTS_DEFAULT_MODEL", "tts-1.7b-custom")

# ── 模型清單 ───────────────────────────────────────────────────────────────────
MODELS = [
    {
        "id": "tts-0.6b-base",
        "name": "TTS-0.6B-Base",
        "repo": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        "type": "base",
        "vram": 2,
        "desc": "輕量語音複製，提供 3 秒參考音訊複製任意音色",
    },
    {
        "id": "tts-1.7b-base",
        "name": "TTS-1.7B-Base",
        "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        "type": "base",
        "vram": 4,
        "desc": "高品質語音複製，提供 3 秒參考音訊複製任意音色",
    },
    {
        "id": "tts-0.6b-custom",
        "name": "TTS-0.6B-CustomVoice",
        "repo": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
        "type": "custom",
        "vram": 2,
        "desc": "輕量版，9 種內建音色 + 自然語言情緒控制",
    },
    {
        "id": "tts-1.7b-custom",
        "name": "TTS-1.7B-CustomVoice",
        "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        "type": "custom",
        "vram": 4,
        "desc": "高品質，9 種內建音色 + 自然語言情緒控制 ✅",
    },
    {
        "id": "tts-1.7b-design",
        "name": "TTS-1.7B-VoiceDesign",
        "repo": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        "type": "design",
        "vram": 4,
        "desc": "用自然語言文字描述設計專屬音色",
    },
]
MODEL_MAP = {m["id"]: m for m in MODELS}

# ── 全域狀態 ───────────────────────────────────────────────────────────────────
state: dict = {
    "model":      None,
    "active_id":  None,
    "loading":    False,
    "loading_id": None,
    "error":      None,
    "loaded_at":  None,
}
_load_lock = asyncio.Lock()

# ── VRAM ───────────────────────────────────────────────────────────────────────
def vram_info() -> dict:
    if not torch.cuda.is_available():
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0}
    prop  = torch.cuda.get_device_properties(0)
    total = prop.total_memory
    alloc = torch.cuda.memory_allocated(0)
    return {
        "total_gb": round(total / 1024**3, 1),
        "used_gb":  round(alloc / 1024**3, 1),
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
        print("[MGR] 已卸載模型，VRAM 已清空")

def _load_sync(model_id: str):
    from qwen_tts import Qwen3TTSModel
    meta = MODEL_MAP[model_id]
    _unload()
    try:
        import flash_attn
        attn = "flash_attention_2"
    except ImportError:
        attn = "eager"
    print(f"[MGR] 載入 {meta['name']}  repo={meta['repo']} ...")
    state["model"] = Qwen3TTSModel.from_pretrained(
        meta["repo"],
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation=attn,
    )
    state["active_id"] = model_id
    state["loaded_at"] = time.time()
    print(f"[MGR] 載入完成：{meta['name']}")

async def _switch(model_id: str):
    async with _load_lock:
        state["loading"]    = True
        state["loading_id"] = model_id
        state["error"]      = None
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _load_sync, model_id)
        except Exception as e:
            state["error"] = str(e)
            print(f"[MGR] 載入失敗：{e}")
        finally:
            state["loading"]    = False
            state["loading_id"] = None

# ── FastAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Qwen3-TTS Manager", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(_switch(DEFAULT_MODEL))

# ── 管理 API ───────────────────────────────────────────────────────────────────
@app.get("/api/models")
def api_models():
    return [
        {**m, "active": m["id"] == state["active_id"], "loading": m["id"] == state["loading_id"]}
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
    asyncio.create_task(_switch(model_id))
    return {"status": "loading", "model_id": model_id}

@app.get("/health")
def health():
    return {"status": "ok", "active_model": state["active_id"], "loading": state["loading"]}

@app.get("/speakers")
def speakers():
    m = state["model"]
    if m is None:
        raise HTTPException(503, "模型尚未載入")
    if MODEL_MAP.get(state["active_id"], {}).get("type") == "base":
        return {"speakers": [], "note": "base 模式請使用 /clone 端點"}
    return {"speakers": m.get_supported_speakers()}

@app.get("/languages")
def languages():
    m = state["model"]
    if m is None:
        raise HTTPException(503, "模型尚未載入")
    if hasattr(m, "get_supported_languages"):
        return {"languages": m.get_supported_languages()}
    return {"languages": ["Chinese","English","Japanese","Korean","German",
                          "French","Russian","Portuguese","Spanish","Italian"]}

# ── 語音合成（custom / design）────────────────────────────────────────────────
class SynthRequest(BaseModel):
    text:     str
    language: str = "Chinese"
    speaker:  str = "Vivian"
    instruct: str = ""

@app.post("/synthesize")
def synthesize(req: SynthRequest):
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    if MODEL_MAP.get(state["active_id"], {}).get("type") == "base":
        raise HTTPException(400, "當前為 base 模式，請使用 /clone 端點")
    wavs, sr = state["model"].generate_custom_voice(
        text=req.text, language=req.language,
        speaker=req.speaker, instruct=req.instruct,
    )
    return Response(content=_wav_bytes(wavs, sr), media_type="audio/wav")

# ── 語音複製（base）──────────────────────────────────────────────────────────
@app.post("/clone")
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

  /* VRAM bar */
  .vram-bar{background:#1e293b;border-radius:8px;padding:14px 18px;margin-bottom:24px;display:flex;align-items:center;gap:16px}
  .vram-label{color:#94a3b8;font-size:.8rem;white-space:nowrap}
  .bar-wrap{flex:1;background:#334155;border-radius:4px;height:8px;overflow:hidden}
  .bar-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6);transition:width .5s}
  .vram-nums{font-size:.8rem;color:#94a3b8;white-space:nowrap}

  /* status badge */
  .status-chip{display:inline-flex;align-items:center;gap:6px;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:6px 14px;font-size:.8rem;margin-bottom:24px}
  .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0}
  .dot.loading{background:#f59e0b;animation:pulse 1s infinite}
  .dot.err{background:#ef4444}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  /* model grid */
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:32px}
  .card{background:#1e293b;border:2px solid #334155;border-radius:12px;padding:18px;transition:border-color .2s}
  .card.active{border-color:#3b82f6;background:#1e3a5f}
  .card.loading-card{border-color:#f59e0b;opacity:.9}
  .card-head{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px}
  .card-name{font-weight:600;font-size:.95rem;color:#f1f5f9}
  .badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}
  .badge{font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:600}
  .badge-base{background:#1e40af;color:#93c5fd}
  .badge-custom{background:#14532d;color:#86efac}
  .badge-design{background:#4c1d95;color:#c4b5fd}
  .badge-active{background:#166534;color:#4ade80}
  .badge-loading{background:#78350f;color:#fcd34d}
  .vram-req{font-size:.75rem;color:#64748b;margin-top:2px}
  .card-desc{font-size:.82rem;color:#94a3b8;line-height:1.5;margin-bottom:14px}
  .btn{width:100%;padding:8px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:opacity .2s}
  .btn-activate{background:#3b82f6;color:#fff}
  .btn-activate:hover{opacity:.85}
  .btn-activate:disabled{background:#334155;color:#64748b;cursor:not-allowed}
  .btn-active{background:#166534;color:#4ade80;cursor:default}
  .btn-loading{background:#78350f;color:#fcd34d;cursor:wait}

  /* test panel */
  .panel{background:#1e293b;border-radius:12px;padding:20px}
  .panel h2{font-size:1rem;font-weight:600;margin-bottom:16px;color:#f1f5f9}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
  label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:4px}
  input,select,textarea{width:100%;background:#0f1117;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px 10px;font-size:.9rem}
  textarea{resize:vertical;min-height:80px}
  .btn-synth{background:#8b5cf6;color:#fff;border:none;border-radius:8px;padding:10px 20px;cursor:pointer;font-size:.9rem;font-weight:600;margin-top:4px}
  .btn-synth:hover{opacity:.85}
  .btn-synth:disabled{opacity:.4;cursor:not-allowed}
  audio{width:100%;margin-top:12px;border-radius:6px}
  .err-msg{color:#f87171;font-size:.82rem;margin-top:8px}
  .note{font-size:.78rem;color:#475569;margin-top:8px}
</style>
</head>
<body>
<h1>Qwen3-TTS 模型管理</h1>
<p class="sub">一次部署，動態切換模型 | 統一 API：<code>POST /synthesize</code> · <code>POST /clone</code></p>

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
  <h2>測試合成</h2>
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
      <label>音色 <span style="color:#475569">(custom/design 模式)</span></label>
      <select id="t-speaker">
        <option>Vivian</option><option>Serena</option><option>Uncle_Fu</option>
        <option>Dylan</option><option>Eric</option><option>Ryan</option>
        <option>Aiden</option><option>Ono_Anna</option><option>Sohee</option>
      </select>
    </div>
  </div>
  <div style="margin-bottom:12px">
    <label>情緒指令 <span style="color:#475569">(選填，如「用特別開心的語氣說」)</span></label>
    <input id="t-instruct" type="text" placeholder="留空則使用預設語氣">
  </div>
  <button class="btn-synth" id="t-btn" onclick="synthesize()">合成語音</button>
  <div class="err-msg" id="t-err"></div>
  <audio id="t-audio" controls style="display:none"></audio>
  <p class="note">base 模式請直接呼叫 <code>POST /clone</code> API，此面板僅支援 custom / design 模式。</p>
</div>

<script>
const BASE = '';
let currentType = null;

async function fetchStatus() {
  try {
    const r = await fetch(BASE + '/api/status');
    const s = await r.json();
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    if (s.loading) {
      dot.className = 'dot loading';
      const lm = s.loading_id || '';
      txt.textContent = `載入中：${lm}...`;
    } else if (s.error) {
      dot.className = 'dot err';
      txt.textContent = `錯誤：${s.error}`;
    } else if (s.active_name) {
      dot.className = 'dot';
      txt.textContent = `啟用中：${s.active_name}`;
      currentType = s.active_type;
    } else {
      dot.className = 'dot err';
      txt.textContent = '尚未載入模型';
    }
    // VRAM
    if (s.vram && s.vram.total_gb > 0) {
      const pct = (s.vram.used_gb / s.vram.total_gb * 100).toFixed(0);
      document.getElementById('vram-fill').style.width = pct + '%';
      document.getElementById('vram-nums').textContent =
        `${s.vram.used_gb} / ${s.vram.total_gb} GB (${pct}%)  ${s.vram.device || ''}`;
    }
    return s;
  } catch(e) { return null; }
}

async function fetchModels() {
  try {
    const r = await fetch(BASE + '/api/models');
    return await r.json();
  } catch(e) { return []; }
}

function typeColor(t) {
  return t === 'base' ? 'badge-base' : t === 'custom' ? 'badge-custom' : 'badge-design';
}

async function renderGrid() {
  const [models, status] = await Promise.all([fetchModels(), fetchStatus()]);
  const grid = document.getElementById('model-grid');
  grid.innerHTML = models.map(m => {
    const isActive  = m.active;
    const isLoading = m.loading;
    let btn = '';
    if (isActive)       btn = `<button class="btn btn-active" disabled>✅ 啟用中</button>`;
    else if (isLoading) btn = `<button class="btn btn-loading" disabled>⏳ 載入中...</button>`;
    else                btn = `<button class="btn btn-activate" onclick="activate('${m.id}')">啟用</button>`;
    return `
    <div class="card ${isActive?'active':''} ${isLoading?'loading-card':''}">
      <div class="card-head">
        <div>
          <div class="card-name">${m.name}</div>
          <div class="badges">
            <span class="badge ${typeColor(m.type)}">${m.type}</span>
            ${isActive  ? '<span class="badge badge-active">啟用中</span>' : ''}
            ${isLoading ? '<span class="badge badge-loading">載入中</span>' : ''}
          </div>
          <div class="vram-req">VRAM ≥ ${m.vram} GB</div>
        </div>
      </div>
      <div class="card-desc">${m.desc}</div>
      ${btn}
    </div>`;
  }).join('');
}

async function activate(id) {
  await fetch(BASE + `/api/models/${id}/activate`, {method:'POST'});
  renderGrid();
}

async function synthesize() {
  const btn = document.getElementById('t-btn');
  const err = document.getElementById('t-err');
  const aud = document.getElementById('t-audio');
  err.textContent = '';
  btn.disabled = true;
  btn.textContent = '合成中...';
  try {
    const body = {
      text:     document.getElementById('t-text').value,
      language: document.getElementById('t-lang').value,
      speaker:  document.getElementById('t-speaker').value,
      instruct: document.getElementById('t-instruct').value,
    };
    const r = await fetch(BASE + '/synthesize', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const j = await r.json();
      err.textContent = j.detail || '合成失敗';
      return;
    }
    const blob = await r.blob();
    aud.src = URL.createObjectURL(blob);
    aud.style.display = 'block';
    aud.play();
  } catch(e) {
    err.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = '合成語音';
  }
}

// 初始渲染 + 每 2 秒更新
renderGrid();
setInterval(renderGrid, 2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"[MGR] Qwen3-TTS Manager — http://0.0.0.0:{PORT}")
    print(f"[MGR] 管理 UI → http://0.0.0.0:{PORT}/")
    print(f"[MGR] 預設模型：{DEFAULT_MODEL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
