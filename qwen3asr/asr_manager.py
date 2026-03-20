"""
asr_manager.py — Qwen3-ASR 統一管理器（OpenAI 相容）
Port: 8002（預設）

認證（與 asr_api.py / tts_manager.py 相同模式）：
  無驗證    API_KEY / API_KEYS 均未設定
  單 Key   API_KEY=sk-xxxx
  多 Key   API_KEYS=sk-a,sk-b,sk-c

主要端點：
  POST /v1/audio/transcriptions   OpenAI Whisper 相容，帶 model 欄位自動切換
  GET  /v1/models                 可用模型清單
  POST /transcribe                上傳音訊辨識
  POST /transcribe/url            URL 音訊辨識
  GET  /health                    健康檢查（不需驗證）

管理端點（不需驗證）：
  GET  /                          管理 UI
  GET  /api/models                所有模型 + 狀態
  GET  /api/status                目前模型 + VRAM
  POST /api/models/{id}/activate  手動切換模型

呼叫範例：
  # OpenAI SDK 相容
  curl -X POST http://localhost:8002/v1/audio/transcriptions \\
    -H "Authorization: Bearer sk-your-key" \\
    -F "file=@audio.wav" \\
    -F "model=asr-1.7b" \\
    -F "language=Chinese"

  # 切換到 0.6B 輕量模型
  curl -X POST http://localhost:8002/v1/audio/transcriptions \\
    -H "Authorization: Bearer sk-your-key" \\
    -F "file=@audio.wav" \\
    -F "model=asr-0.6b"

環境變數：
  API_KEY             單一 API Key
  API_KEYS            多 API Key（逗號分隔）
  ASR_DEFAULT_MODEL   啟動預載模型 ID（預設 asr-1.7b）
  ASR_TIMESTAMPS      預設啟用時間戳記 true/false（預設 false）
"""
import sys, os, gc, asyncio, tempfile, time, threading
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Depends, Security, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader

PORT            = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
DEFAULT_MODEL   = os.environ.get("ASR_DEFAULT_MODEL", "asr-1.7b")
DEFAULT_TS      = os.environ.get("ASR_TIMESTAMPS", "false").lower() == "true"

# ── 模型清單 ───────────────────────────────────────────────────────────────────
MODELS = [
    {
        "id":   "asr-0.6b",
        "name": "Qwen3-ASR-0.6B",
        "repo": "Qwen/Qwen3-ASR-0.6B",
        "vram": 2,
        "desc": "輕量快速，適合即時轉錄，30 種語言 + 22 種中文方言",
    },
    {
        "id":   "asr-1.7b",
        "name": "Qwen3-ASR-1.7B",
        "repo": "Qwen/Qwen3-ASR-1.7B",
        "vram": 4,
        "desc": "高精度，推薦使用 ✅，30 種語言 + 22 種中文方言",
    },
]
MODEL_MAP = {m["id"]: m for m in MODELS}
ALIGNER_REPO = "Qwen/Qwen3-ForcedAligner-0.6B"

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
    "timestamps": DEFAULT_TS,
}
_load_lock  = threading.Lock()
_async_lock = asyncio.Lock()

# ── 系統資訊（VRAM / GPU% / CPU% / RAM）──────────────────────────────────────
def sys_info() -> dict:
    info: dict = {
        "vram":    {"total_gb": 0, "used_gb": 0, "free_gb": 0, "device": "N/A"},
        "gpu_pct": None,
        "cpu_pct": None,
        "ram":     None,
    }
    try:
        if torch.cuda.is_available():
            prop  = torch.cuda.get_device_properties(0)
            total = prop.total_memory
            alloc = torch.cuda.memory_allocated(0)
            info["vram"] = {
                "total_gb": round(total / 1024**3, 1),
                "used_gb":  round(alloc  / 1024**3, 1),
                "free_gb":  round((total - alloc) / 1024**3, 1),
                "device":   prop.name,
            }
            try:
                info["gpu_pct"] = torch.cuda.utilization()
            except Exception:
                info["gpu_pct"] = None
    except Exception:
        pass
    try:
        import psutil
        info["cpu_pct"] = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        info["ram"] = {
            "total_gb": round(vm.total / 1024**3, 1),
            "used_gb":  round(vm.used  / 1024**3, 1),
            "pct":      vm.percent,
        }
    except Exception:
        pass
    return info

# ── 模型操作 ───────────────────────────────────────────────────────────────────
def _unload():
    if state["model"] is not None:
        del state["model"]
        state["model"] = None
        gc.collect()
        torch.cuda.empty_cache()
        print("[MGR] 模型已卸載，VRAM 已清空")

def _load_sync(model_id: str, use_timestamps: bool | None = None):
    with _load_lock:
        if state["active_id"] == model_id and state["model"] is not None:
            return
        from qwen_asr import Qwen3ASRModel
        meta = MODEL_MAP[model_id]
        state["loading"]    = True
        state["loading_id"] = model_id
        state["error"]      = None
        ts = use_timestamps if use_timestamps is not None else state["timestamps"]
        try:
            _unload()
            try:
                import flash_attn
                attn = "flash_attention_2"
            except ImportError:
                attn = "eager"
            print(f"[MGR] 載入 {meta['name']}  timestamps={ts} ...")
            kwargs = dict(
                dtype=torch.bfloat16,
                device_map="cuda:0",
                max_inference_batch_size=16,
                max_new_tokens=1024,
                attn_implementation=attn,
            )
            if ts:
                kwargs["forced_aligner"] = ALIGNER_REPO
                kwargs["forced_aligner_kwargs"] = dict(
                    dtype=torch.bfloat16, device_map="cuda:0"
                )
            state["model"]     = Qwen3ASRModel.from_pretrained(meta["repo"], **kwargs)
            state["active_id"] = model_id
            state["loaded_at"] = time.time()
            state["timestamps"] = ts
            print(f"[MGR] 載入完成：{meta['name']}")
        except Exception as e:
            state["error"] = str(e)
            print(f"[MGR] 載入失敗：{e}")
            raise
        finally:
            state["loading"]    = False
            state["loading_id"] = None

async def _bg_load(model_id: str, use_timestamps: bool | None = None):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_sync, model_id, use_timestamps)

async def ensure_model(model_id: str):
    if state["active_id"] == model_id and state["model"] is not None:
        return
    async with _async_lock:
        if state["active_id"] == model_id and state["model"] is not None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_sync, model_id)
        if state["error"]:
            raise HTTPException(500, f"模型載入失敗：{state['error']}")

# ── 轉錄邏輯 ───────────────────────────────────────────────────────────────────
def _do_transcribe(audio_path: str, language: str | None, want_ts: bool) -> dict:
    results = state["model"].transcribe(
        audio=audio_path,
        language=language or None,
        return_time_stamps=want_ts and state["timestamps"],
    )
    r = results[0]
    resp = {"text": r.text, "language": r.language}
    if want_ts and state["timestamps"] and getattr(r, "segments", None):
        resp["segments"] = [
            {"text": s.text, "start": round(s.start_time, 3), "end": round(s.end_time, 3)}
            for s in r.segments
        ]
    return resp

# ── FastAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Qwen3-ASR Manager",
    version="2.0",
    description="統一 ASR API，支援 2 種模型熱切換與 OpenAI Whisper 相容格式",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(_bg_load(DEFAULT_MODEL))

# ── OpenAI 相容端點 ────────────────────────────────────────────────────────────
@app.post("/v1/audio/transcriptions", dependencies=[Depends(verify_key)])
async def v1_transcriptions(
    file:                    UploadFile = File(...),
    model:                   str        = Form(default="asr-1.7b"),
    language:                str        = Form(default=None),
    response_format:         str        = Form(default="json"),
    timestamp_granularities: str        = Form(default=""),
):
    if model not in MODEL_MAP:
        raise HTTPException(400, f"未知模型：{model}。可用：{list(MODEL_MAP)}")
    await ensure_model(model)
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
        return PlainTextResponse(result["text"])
    if response_format == "verbose_json":
        return {"task": "transcribe", "language": result.get("language", ""),
                "text": result["text"], "segments": result.get("segments", [])}
    return {"text": result["text"]}

@app.get("/v1/models", dependencies=[Depends(verify_key)])
def v1_models():
    return {
        "object": "list",
        "data": [
            {"id": m["id"], "object": "model", "vram_gb": m["vram"], "description": m["desc"]}
            for m in MODELS
        ],
    }

# ── 舊版端點（向後相容）────────────────────────────────────────────────────────
@app.post("/transcribe", dependencies=[Depends(verify_key)])
async def transcribe(
    file:       UploadFile = File(...),
    language:   str        = Form(default=None),
    timestamps: bool       = Form(default=False),
):
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    suffix = os.path.splitext(file.filename)[-1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return _do_transcribe(tmp_path, language, timestamps)
    finally:
        os.unlink(tmp_path)

@app.post("/transcribe/url", dependencies=[Depends(verify_key)])
async def transcribe_url(
    url:        str  = Form(...),
    language:   str  = Form(default=None),
    timestamps: bool = Form(default=False),
):
    if state["model"] is None:
        raise HTTPException(503, "模型尚未載入")
    return _do_transcribe(url, language, timestamps)

# ── 工具端點 ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "active_model": state["active_id"],
            "loading": state["loading"], "timestamps": state["timestamps"],
            "auth": AUTH_ENABLED}

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
        "active_id":    state["active_id"],
        "active_name":  active["name"] if active else None,
        "loading":      state["loading"],
        "loading_id":   state["loading_id"],
        "error":        state["error"],
        "timestamps":   state["timestamps"],
        "auth_enabled": AUTH_ENABLED,
        **sys_info(),
    }

@app.post("/api/models/{model_id}/activate")
async def api_activate(model_id: str, timestamps: bool = False):
    if model_id not in MODEL_MAP:
        raise HTTPException(404, f"未知模型 ID：{model_id}")
    if state["loading"]:
        raise HTTPException(409, "另一個模型正在載入中，請稍候")
    if state["active_id"] == model_id and state["model"] is not None:
        return {"status": "already_active", "model_id": model_id}
    asyncio.create_task(_bg_load(model_id, timestamps))
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
<title>Qwen3-ASR 模型管理</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh;padding:24px}
  h1{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px}
  .sub{color:#64748b;font-size:.85rem;margin-bottom:24px}
  code{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:.82rem}

  .info-bar{background:#1e293b;border-radius:8px;padding:14px 18px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
  .info-item{font-size:.82rem;color:#94a3b8}
  .info-item b{color:#e2e8f0}

  .gauges{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-bottom:24px}
  .gauge{background:#1e293b;border-radius:8px;padding:12px 16px}
  .gauge-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
  .gauge-label{color:#94a3b8;font-size:.78rem}
  .gauge-val{font-size:.78rem;color:#e2e8f0;font-weight:600}
  .bar-wrap{background:#334155;border-radius:4px;height:6px;overflow:hidden}
  .bar-fill{height:100%;border-radius:4px;transition:width .5s}
  .bar-vram{background:linear-gradient(90deg,#3b82f6,#8b5cf6)}
  .bar-gpu {background:linear-gradient(90deg,#10b981,#06b6d4)}
  .bar-cpu {background:linear-gradient(90deg,#f59e0b,#ef4444)}
  .bar-ram {background:linear-gradient(90deg,#8b5cf6,#ec4899)}
  .gauge-sub{font-size:.72rem;color:#475569;margin-top:4px}

  .status-chip{display:inline-flex;align-items:center;gap:6px;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:6px 14px;font-size:.8rem;margin-bottom:24px}
  .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0}
  .dot.loading{background:#f59e0b;animation:pulse 1s infinite}
  .dot.err{background:#ef4444}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:32px}
  .card{background:#1e293b;border:2px solid #334155;border-radius:12px;padding:18px;transition:border-color .2s}
  .card.active{border-color:#10b981;background:#052e16}
  .card.loading-card{border-color:#f59e0b}
  .card-name{font-weight:600;font-size:.95rem;color:#f1f5f9;margin-bottom:6px}
  .badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
  .badge{font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:600}
  .badge-active{background:#166534;color:#4ade80}
  .badge-loading{background:#78350f;color:#fcd34d}
  .vram-req{font-size:.75rem;color:#64748b;margin-bottom:8px}
  .card-desc{font-size:.82rem;color:#94a3b8;line-height:1.5;margin-bottom:14px}
  .card-opts{display:flex;align-items:center;gap:8px;margin-bottom:10px;font-size:.82rem;color:#94a3b8}
  .btn{width:100%;padding:8px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:opacity .2s}
  .btn-activate{background:#10b981;color:#fff}.btn-activate:hover{opacity:.85}
  .btn-activate:disabled{background:#334155;color:#64748b;cursor:not-allowed}
  .btn-active{background:#166534;color:#4ade80;cursor:default}
  .btn-loading{background:#78350f;color:#fcd34d;cursor:wait}

  .panel{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px}
  .panel h2{font-size:1rem;font-weight:600;margin-bottom:16px;color:#f1f5f9}
  label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:4px}
  input,select{width:100%;background:#0f1117;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px 10px;font-size:.9rem;margin-bottom:12px}
  .btn-upload{background:#3b82f6;color:#fff;border:none;border-radius:8px;padding:10px 20px;cursor:pointer;font-size:.9rem;font-weight:600}
  .btn-upload:hover{opacity:.85}.btn-upload:disabled{opacity:.4;cursor:not-allowed}
  .result-box{background:#0f1117;border:1px solid #334155;border-radius:6px;padding:12px;margin-top:12px;font-size:.9rem;line-height:1.6;white-space:pre-wrap;word-break:break-all;display:none}
  .err-msg{color:#f87171;font-size:.82rem;margin-top:8px}
  .note{font-size:.78rem;color:#475569;margin-top:8px}
</style>
</head>
<body>
<h1>Qwen3-ASR 模型管理</h1>
<p class="sub">Frontend 整合：設定 API URL + API Key，請求帶 <code>model</code> 欄位自動切換</p>

<div class="info-bar">
  <div class="info-item">API URL <b id="info-url">—</b></div>
  <div class="info-item">認證 <b id="info-auth">—</b></div>
  <div class="info-item">端點 <code>POST /v1/audio/transcriptions</code></div>
  <div class="info-item">文件 <a href="/docs" style="color:#60a5fa">/docs</a></div>
</div>

<div class="gauges">
  <div class="gauge">
    <div class="gauge-head"><span class="gauge-label">GPU VRAM</span><span class="gauge-val" id="vram-val">—</span></div>
    <div class="bar-wrap"><div class="bar-fill bar-vram" id="vram-fill" style="width:0%"></div></div>
    <div class="gauge-sub" id="vram-dev">—</div>
  </div>
  <div class="gauge">
    <div class="gauge-head"><span class="gauge-label">GPU 使用率</span><span class="gauge-val" id="gpu-val">—</span></div>
    <div class="bar-wrap"><div class="bar-fill bar-gpu" id="gpu-fill" style="width:0%"></div></div>
    <div class="gauge-sub" id="gpu-sub">—</div>
  </div>
  <div class="gauge">
    <div class="gauge-head"><span class="gauge-label">CPU 使用率</span><span class="gauge-val" id="cpu-val">—</span></div>
    <div class="bar-wrap"><div class="bar-fill bar-cpu" id="cpu-fill" style="width:0%"></div></div>
    <div class="gauge-sub" id="cpu-sub">—</div>
  </div>
  <div class="gauge">
    <div class="gauge-head"><span class="gauge-label">記憶體 RAM</span><span class="gauge-val" id="ram-val">—</span></div>
    <div class="bar-wrap"><div class="bar-fill bar-ram" id="ram-fill" style="width:0%"></div></div>
    <div class="gauge-sub" id="ram-sub">—</div>
  </div>
</div>

<div class="status-chip">
  <span class="dot" id="status-dot"></span>
  <span id="status-text">初始化中...</span>
</div>

<div class="grid" id="model-grid"></div>

<div class="panel">
  <h2>測試辨識（對應 POST /v1/audio/transcriptions）</h2>
  <label>音訊檔案</label>
  <input type="file" id="t-file" accept="audio/*">
  <label>語言（留空自動偵測）</label>
  <select id="t-lang">
    <option value="">自動偵測</option>
    <option>Chinese</option><option>Cantonese</option><option>English</option>
    <option>Japanese</option><option>Korean</option><option>German</option>
    <option>French</option><option>Russian</option><option>Spanish</option>
    <option>Portuguese</option><option>Italian</option>
  </select>
  <label style="display:flex;align-items:center;gap:8px;margin-bottom:12px;cursor:pointer">
    <input type="checkbox" id="t-ts" style="width:auto;margin:0"> 回傳時間戳記
  </label>
  <button class="btn-upload" id="t-btn" onclick="transcribe()">▶ 開始辨識</button>
  <div class="err-msg" id="t-err"></div>
  <div class="result-box" id="t-result"></div>
  <p class="note">使用當前啟用的模型。時間戳記需模型啟用時勾選「啟用時間戳記」。</p>
</div>

<script>
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) { console.error('[ASR] /api/status', res.status, await res.text()); return null; }
    const s = await res.json();
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
      const ts = s.timestamps ? '  時間戳記：ON' : '';
      txt.textContent = `啟用中：${s.active_name}${ts}`;
    } else {
      dot.className = 'dot err';
      txt.textContent = '尚未載入模型';
    }
    if (s.vram && s.vram.total_gb > 0) {
      const pct = (s.vram.used_gb / s.vram.total_gb * 100).toFixed(0);
      document.getElementById('vram-fill').style.width = pct + '%';
      document.getElementById('vram-val').textContent = `${s.vram.used_gb} / ${s.vram.total_gb} GB (${pct}%)`;
      document.getElementById('vram-dev').textContent = s.vram.device || '—';
    }
    if (s.gpu_pct != null) {
      document.getElementById('gpu-fill').style.width = s.gpu_pct + '%';
      document.getElementById('gpu-val').textContent = s.gpu_pct + '%';
      document.getElementById('gpu-sub').textContent = s.gpu_pct > 80 ? '高負載' : s.gpu_pct > 40 ? '中負載' : '低負載';
    }
    if (s.cpu_pct != null) {
      document.getElementById('cpu-fill').style.width = s.cpu_pct + '%';
      document.getElementById('cpu-val').textContent = s.cpu_pct.toFixed(1) + '%';
      document.getElementById('cpu-sub').textContent = s.cpu_pct > 80 ? '高負載' : s.cpu_pct > 40 ? '中負載' : '低負載';
    }
    if (s.ram) {
      document.getElementById('ram-fill').style.width = s.ram.pct + '%';
      document.getElementById('ram-val').textContent = `${s.ram.used_gb} / ${s.ram.total_gb} GB (${s.ram.pct}%)`;
      document.getElementById('ram-sub').textContent = s.ram.pct > 85 ? '記憶體緊張' : '正常';
    }
    document.getElementById('info-url').textContent = location.origin;
    document.getElementById('info-auth').textContent = s.auth_enabled ? '已啟用（API Key）' : '未啟用';
    return s;
  } catch(e) { console.error('[ASR] fetchStatus error:', e); return null; }
}

async function renderGrid() {
  const [models] = await Promise.all([
    fetch('/api/models').then(r => r.json()),
    fetchStatus(),
  ]);
  const grid = document.getElementById('model-grid');
  grid.innerHTML = models.map(m => {
    let btn = m.active
      ? `<button class="btn btn-active" disabled>✅ 啟用中</button>`
      : m.loading
        ? `<button class="btn btn-loading" disabled>⏳ 載入中...</button>`
        : `<div class="card-opts">
             <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:#94a3b8">
               <input type="checkbox" id="ts-${m.id}" style="cursor:pointer"> 啟用時間戳記
             </label>
           </div>
           <button class="btn btn-activate" onclick="activate('${m.id}')">啟用</button>`;
    return `<div class="card ${m.active?'active':''} ${m.loading?'loading-card':''}">
      <div class="card-name">${m.name}</div>
      <div class="badges">
        ${m.active  ? '<span class="badge badge-active">啟用中</span>' : ''}
        ${m.loading ? '<span class="badge badge-loading">載入中</span>' : ''}
      </div>
      <div class="vram-req">VRAM ≥ ${m.vram} GB</div>
      <div class="card-desc">${m.desc}</div>${btn}</div>`;
  }).join('');
}

async function activate(id) {
  const ts = document.getElementById(`ts-${id}`)?.checked || false;
  await fetch(`/api/models/${id}/activate?timestamps=${ts}`, {method:'POST'});
  renderGrid();
}

async function transcribe() {
  const btn  = document.getElementById('t-btn');
  const err  = document.getElementById('t-err');
  const res  = document.getElementById('t-result');
  const file = document.getElementById('t-file').files[0];
  if (!file) { err.textContent = '請先選擇音訊檔案'; return; }
  err.textContent = ''; res.style.display = 'none';
  btn.disabled = true; btn.textContent = '辨識中...';
  try {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('language', document.getElementById('t-lang').value);
    const wantTs = document.getElementById('t-ts').checked;
    if (wantTs) fd.append('timestamp_granularities', 'segment');
    fd.append('response_format', wantTs ? 'verbose_json' : 'json');
    const status = await fetch('/api/status').then(r => r.json());
    fd.append('model', status.active_id || 'asr-1.7b');
    const r = await fetch('/v1/audio/transcriptions', {method:'POST', body: fd});
    if (!r.ok) { err.textContent = (await r.json()).detail || '辨識失敗'; return; }
    const j = await r.json();
    let out = `語言：${j.language || '—'}\\n文字：${j.text}`;
    if (j.segments?.length) {
      out += '\\n\\n時間戳記：\\n' + j.segments.map(s =>
        `  [${s.start.toFixed(2)}s - ${s.end.toFixed(2)}s] ${s.text}`
      ).join('\\n');
    }
    res.textContent = out; res.style.display = 'block';
  } catch(e) { err.textContent = e.message; }
  finally { btn.disabled = false; btn.textContent = '▶ 開始辨識'; }
}

renderGrid();
setInterval(renderGrid, 2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"[MGR] Qwen3-ASR Manager v2  — http://0.0.0.0:{PORT}/")
    print(f"[MGR] 預載模型：{DEFAULT_MODEL}  timestamps={DEFAULT_TS}")
    print(f"[MGR] 認證：{'已啟用' if AUTH_ENABLED else '未啟用（設定 API_KEY=sk-xxx 啟用）'}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
