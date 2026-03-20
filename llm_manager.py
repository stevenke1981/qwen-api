"""
llm_manager.py — Qwen LLM 統一管理器（OpenAI 相容，反向代理 llama-server）
Port: 8000（預設，取代直接執行 llama-server）

功能：
  - 管理 llama-server 子進程（啟動 / 停止 / 熱切換模型）
  - 反向代理所有 /v1/* 請求至 llama-server（含 SSE streaming）
  - API Key 驗證（與 ASR/TTS Manager 相同模式）
  - 內建管理 UI，顯示 GPU VRAM / 使用率 / CPU / RAM

端點：
  GET  /                         管理 UI
  GET  /api/models               所有模型 + 狀態（含檔案存在檢查）
  GET  /api/status               目前模型 + 系統資訊
  POST /api/models/{id}/activate 切換模型（背景執行）
  GET  /health                   健康檢查（不需驗證）
  *    /v1/*                     透明代理至 llama-server

環境變數：
  API_KEY             單一 API Key
  API_KEYS            多 API Key（逗號分隔）
  LLM_DEFAULT_MODEL   啟動預載模型 ID（預設 chat）
  MODEL_DIR           GGUF 模型目錄（預設 ~/models）
  LLAMA_PORT          llama-server 內部 port（預設 8010）

模型 ID 對照：
  chat           Qwen3.5-4B Q5_K_M       — 通用對話（預設）
  chat-9b        Qwen3.5-9B Q5_K_M       — 通用對話 9B
  coder-7b       Qwen2.5-Coder-7B Q8_0  — coding 優化
  coder-14b      Qwen2.5-Coder-14B Q4   — coding 高品質
  coder-14b-q8   Qwen2.5-Coder-14B Q8   — coding 最高（需 16 GB）
  openclaw       Qwen3.5-9B-Uncensored   — OpenClaw agent
  openclaw-fast  Qwen3.5-9B Q3_K_M      — OpenClaw 極速
"""
import sys, os, gc, asyncio, json, time, subprocess, threading
import torch
import httpx
import uvicorn
from fastapi import FastAPI, Depends, Security, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.api_key import APIKeyHeader

PORT        = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
LLAMA_PORT  = int(os.environ.get("LLAMA_PORT", "8010"))
LLAMA_URL   = f"http://127.0.0.1:{LLAMA_PORT}"
MODEL_DIR   = os.path.expanduser(os.environ.get("MODEL_DIR", "~/models"))
DEFAULT_MODEL = os.environ.get("LLM_DEFAULT_MODEL", "chat")  # chat = Qwen3.5-4B

# ── 模型清單 ───────────────────────────────────────────────────────────────────
MODELS = [
    {
        "id":       "chat",
        "name":     "Qwen3.5-4B Q5_K_M",
        "file":     "Qwen_Qwen3.5-4B-Q5_K_M.gguf",
        "size":     "3.09 GB",
        "vram":     4,
        "ctx":      32768,
        "desc":     "通用對話，思考模式支援，低 VRAM 首選（預設）",
        "flags":    [],
    },
    {
        "id":       "chat-9b",
        "name":     "Qwen3.5-9B Q5_K_M",
        "file":     "Qwen_Qwen3.5-9B-Q5_K_M.gguf",
        "size":     "6.86 GB",
        "vram":     8,
        "ctx":      32768,
        "desc":     "通用對話，思考模式支援，均衡品質與速度",
        "flags":    [],
    },
    {
        "id":       "coder-7b",
        "name":     "Qwen2.5-Coder-7B Q8_0",
        "file":     "qwen2.5-coder-7b-instruct-q8_0.gguf",
        "size":     "8.10 GB",
        "vram":     9,
        "ctx":      32768,
        "desc":     "coding 優化，速度快，適合即時補全",
        "flags":    [],
    },
    {
        "id":       "coder-14b",
        "name":     "Qwen2.5-Coder-14B Q4_K_M",
        "file":     "qwen2.5-coder-14b-instruct-q4_k_m.gguf",
        "size":     "8.99 GB",
        "vram":     10,
        "ctx":      32768,
        "desc":     "coding 優化，品質佳，14B 參數量",
        "flags":    [],
    },
    {
        "id":       "coder-14b-q8",
        "name":     "Qwen2.5-Coder-14B Q8_0",
        "file":     "qwen2.5-coder-14b-instruct-q8_0.gguf",
        "size":     "15.7 GB",
        "vram":     16,
        "ctx":      32768,
        "desc":     "coding 最高品質，需 16 GB VRAM",
        "flags":    [],
    },
    {
        "id":       "openclaw",
        "name":     "Qwen3.5-9B Uncensored Q4_K_M",
        "file":     "Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "size":     "~6 GB",
        "vram":     8,
        "ctx":      65536,
        "desc":     "OpenClaw / coding agent，對指令高服從性，ctx 64k",
        "flags":    ["--n-predict", "2048"],
    },
    {
        "id":       "openclaw-fast",
        "name":     "Qwen3.5-9B Q3_K_M（極速）",
        "file":     "Qwen_Qwen3.5-9B-Q3_K_M.gguf",
        "size":     "~5 GB",
        "vram":     7,
        "ctx":      65536,
        "desc":     "OpenClaw 極速模式，Q3_K_M 量化，VRAM ~6.5 GB",
        "flags":    ["--n-predict", "2048", "--cache-type-k", "q4_0", "--cache-type-v", "q4_0"],
    },
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
    "process":    None,    # subprocess.Popen
    "active_id":  None,
    "loading":    False,
    "loading_id": None,
    "error":      None,
    "started_at": None,
}
_load_lock  = threading.Lock()
_async_lock = asyncio.Lock()

# ── 系統資訊 ───────────────────────────────────────────────────────────────────
def sys_info() -> dict:
    info: dict = {
        "vram":    {"total_gb": 0, "used_gb": 0, "free_gb": 0, "device": "N/A"},
        "gpu_pct": None, "cpu_pct": None, "ram": None,
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
                pass
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

def model_path(m: dict) -> str:
    return os.path.join(MODEL_DIR, m["file"])

def model_available(m: dict) -> bool:
    return os.path.exists(model_path(m))

def scan_model_dir() -> list[dict]:
    """掃描 MODEL_DIR，回傳所有 .gguf 檔案（含是否已在 MODELS 清單）"""
    if not os.path.isdir(MODEL_DIR):
        return []
    known_files = {m["file"]: m["id"] for m in MODELS}
    results = []
    for fname in sorted(os.listdir(MODEL_DIR)):
        if not fname.endswith(".gguf"):
            continue
        fpath = os.path.join(MODEL_DIR, fname)
        try:
            size_gb = round(os.path.getsize(fpath) / 1024**3, 2)
        except OSError:
            size_gb = 0
        matched_id = known_files.get(fname)
        results.append({
            "file":       fname,
            "size_gb":    size_gb,
            "size":       f"{size_gb} GB",
            "matched_id": matched_id,
            "path":       fpath,
        })
    return results

def _dyn_id(fname: str) -> str:
    """從檔名產生動態模型 ID，例：Qwen3.5-4B-Q5_K_M.gguf → dyn-Qwen3.5-4B-Q5_K_M"""
    return "dyn-" + fname.removesuffix(".gguf")

def _register_dyn(fname: str) -> dict:
    """將掃描到的 .gguf 檔動態加入 MODEL_MAP（若已存在則直接回傳）"""
    mid = _dyn_id(fname)
    if mid in MODEL_MAP:
        return MODEL_MAP[mid]
    meta = {
        "id":    mid,
        "name":  fname.removesuffix(".gguf"),
        "file":  fname,
        "size":  "—",
        "vram":  0,
        "ctx":   32768,
        "desc":  "掃描自模型目錄",
        "flags": [],
    }
    MODELS.append(meta)
    MODEL_MAP[mid] = meta
    return meta

# ── llama-server 進程管理 ──────────────────────────────────────────────────────
def _kill_current():
    p = state["process"]
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill()
    state["process"]   = None
    state["active_id"] = None

def _wait_ready(timeout: int = 90) -> bool:
    """輪詢 llama-server /health 直到就緒"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{LLAMA_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def _load_sync(model_id: str):
    with _load_lock:
        if state["active_id"] == model_id and state["process"] and state["process"].poll() is None:
            return
        meta = MODEL_MAP[model_id]
        state["loading"]    = True
        state["loading_id"] = model_id
        state["error"]      = None
        try:
            mpath = model_path(meta)
            if not os.path.exists(mpath):
                raise FileNotFoundError(f"模型檔案不存在：{mpath}")
            _kill_current()
            env = {**os.environ, "PATH": os.environ.get("PATH", "")}
            cmd = [
                "llama-server",
                "--model",         mpath,
                "--host",          "127.0.0.1",
                "--port",          str(LLAMA_PORT),
                "--n-gpu-layers",  "-1",
                "--ctx-size",      str(meta["ctx"]),
                "--batch-size",    "1024",
                "--ubatch-size",   "512",
                "--cache-type-k",  "q8_0",
                "--cache-type-v",  "q8_0",
                "--flash-attn",    "on",
                "--jinja",
            ] + meta.get("flags", [])
            print(f"[LLM] 啟動 llama-server：{meta['name']} ...")
            state["process"] = subprocess.Popen(
                cmd, env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if not _wait_ready(timeout=120):
                raise RuntimeError("llama-server 啟動逾時（120s）")
            state["active_id"] = model_id
            state["started_at"] = time.time()
            print(f"[LLM] 就緒：{meta['name']}")
        except Exception as e:
            state["error"] = str(e)
            print(f"[LLM] 載入失敗：{e}")
            raise
        finally:
            state["loading"]    = False
            state["loading_id"] = None

async def _bg_load(model_id: str):
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _load_sync, model_id)
    except Exception:
        pass  # 錯誤已存入 state["error"]，不需要再拋出

async def ensure_model(model_id: str):
    if state["active_id"] == model_id and state["process"] and state["process"].poll() is None:
        return
    async with _async_lock:
        if state["active_id"] == model_id and state["process"] and state["process"].poll() is None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_sync, model_id)
        if state["error"]:
            raise HTTPException(500, f"模型啟動失敗：{state['error']}")

# ── FastAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Qwen LLM Manager", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    meta = MODEL_MAP.get(DEFAULT_MODEL)
    if meta and os.path.exists(model_path(meta)):
        asyncio.create_task(_bg_load(DEFAULT_MODEL))
    else:
        print(f"[LLM] 預載模型 '{DEFAULT_MODEL}' 檔案不存在，跳過自動載入")
        print(f"[LLM] 請至管理 UI 掃描目錄後選擇可用模型")

@app.on_event("shutdown")
async def _shutdown():
    _kill_current()

# ── 反向代理（/v1/*）────────────────────────────────────────────────────────────
PROXY_PATHS = {"/v1/", "/props", "/slots", "/metrics", "/lora-adapters"}

@app.api_route("/v1/{path:path}", methods=["GET","POST","PUT","DELETE","OPTIONS"])
async def proxy_v1(path: str, request: Request, _: None = Depends(verify_key)):
    if state["process"] is None or state["process"].poll() is not None:
        raise HTTPException(503, "llama-server 尚未啟動，請稍候或切換模型")
    target = f"{LLAMA_URL}/v1/{path}"
    return await _proxy(request, target)

@app.get("/props")
@app.get("/metrics")
async def proxy_misc(request: Request, _: None = Depends(verify_key)):
    return await _proxy(request, f"{LLAMA_URL}{request.url.path}")

async def _proxy(request: Request, target: str) -> Response:
    body = await request.body()
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "authorization", "x-api-key")
    }
    params = dict(request.query_params)
    # 判斷是否為 SSE streaming
    is_stream = False
    if body:
        try:
            is_stream = json.loads(body).get("stream", False)
        except Exception:
            pass
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        if is_stream:
            async def generate():
                async with client.stream(
                    request.method, target,
                    content=body, headers=headers, params=params,
                ) as r:
                    async for chunk in r.aiter_raw():
                        yield chunk
            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            r = await client.request(
                request.method, target,
                content=body, headers=headers, params=params,
            )
            return Response(
                content=r.content,
                status_code=r.status_code,
                headers={k: v for k, v in r.headers.items()
                         if k.lower() not in ("content-length", "transfer-encoding")},
                media_type=r.headers.get("content-type"),
            )

# ── 管理 API ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    proc_alive = state["process"] and state["process"].poll() is None
    return {
        "status":       "ok" if proc_alive else "starting",
        "active_model": state["active_id"],
        "loading":      state["loading"],
        "auth":         AUTH_ENABLED,
    }

@app.get("/api/models")
def api_models():
    return [
        {
            **{k: v for k, v in m.items() if k != "flags"},
            "path":      model_path(m),
            "available": model_available(m),
            "active":    m["id"] == state["active_id"],
            "loading":   m["id"] == state["loading_id"],
        }
        for m in MODELS
    ]

@app.get("/api/status")
def api_status():
    active = MODEL_MAP.get(state["active_id"]) if state["active_id"] else None
    proc_alive = state["process"] and state["process"].poll() is None
    return {
        "active_id":    state["active_id"],
        "active_name":  active["name"] if active else None,
        "loading":      state["loading"],
        "loading_id":   state["loading_id"],
        "error":        state["error"],
        "server_alive": bool(proc_alive),
        "auth_enabled": AUTH_ENABLED,
        **sys_info(),
    }

@app.post("/api/models/{model_id}/activate")
async def api_activate(model_id: str):
    if model_id not in MODEL_MAP:
        raise HTTPException(404, f"未知模型 ID：{model_id}")
    if not model_available(MODEL_MAP[model_id]):
        raise HTTPException(400, f"模型檔案不存在：{model_path(MODEL_MAP[model_id])}")
    if state["loading"]:
        raise HTTPException(409, "另一個模型正在載入中，請稍候")
    if state["active_id"] == model_id and state["process"] and state["process"].poll() is None:
        return {"status": "already_active", "model_id": model_id}
    asyncio.create_task(_bg_load(model_id))
    return {"status": "loading", "model_id": model_id}

@app.get("/api/scan")
def api_scan():
    """掃描 MODEL_DIR，回傳所有 .gguf 檔案清單"""
    files = scan_model_dir()
    return {
        "model_dir": MODEL_DIR,
        "count":     len(files),
        "files":     files,
    }

@app.post("/api/load-file")
async def api_load_file(body: dict):
    """直接載入掃描到的 .gguf 檔（動態註冊後啟動）"""
    fname = body.get("file", "").strip()
    if not fname or not fname.endswith(".gguf"):
        raise HTTPException(400, "請提供有效的 .gguf 檔名")
    fpath = os.path.join(MODEL_DIR, fname)
    if not os.path.exists(fpath):
        raise HTTPException(404, f"檔案不存在：{fpath}")
    if state["loading"]:
        raise HTTPException(409, "另一個模型正在載入中，請稍候")
    meta = _register_dyn(fname)
    asyncio.create_task(_bg_load(meta["id"]))
    return {"status": "loading", "model_id": meta["id"], "file": fname}

# ── 管理 UI ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def ui():
    return HTMLResponse(content=MANAGER_UI)

MANAGER_UI = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen LLM 模型管理</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh;padding:24px}
  h1{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:4px}
  .sub{color:#64748b;font-size:.85rem;margin-bottom:24px}
  code{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:.82rem}
  a{color:#60a5fa}

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
  .bar-gpu{background:linear-gradient(90deg,#10b981,#06b6d4)}
  .bar-cpu{background:linear-gradient(90deg,#f59e0b,#ef4444)}
  .bar-ram{background:linear-gradient(90deg,#8b5cf6,#ec4899)}
  .gauge-sub{font-size:.72rem;color:#475569;margin-top:4px}

  .status-chip{display:inline-flex;align-items:center;gap:6px;background:#1e293b;border:1px solid #334155;border-radius:20px;padding:6px 14px;font-size:.8rem;margin-bottom:24px}
  .dot{width:8px;height:8px;border-radius:50%;background:#22c55e;flex-shrink:0}
  .dot.loading{background:#f59e0b;animation:pulse 1s infinite}
  .dot.err{background:#ef4444}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:24px}
  .card{background:#1e293b;border:2px solid #334155;border-radius:12px;padding:18px;transition:border-color .2s}
  .card.active{border-color:#f59e0b;background:#1c1a07}
  .card.loading-card{border-color:#3b82f6}
  .card.unavailable{opacity:.5}
  .card-name{font-weight:600;font-size:.95rem;color:#f1f5f9;margin-bottom:4px}
  .badges{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px}
  .badge{font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:600}
  .badge-active{background:#713f12;color:#fde68a}
  .badge-loading{background:#1e3a8a;color:#93c5fd}
  .badge-unavailable{background:#1e293b;color:#64748b}
  .meta{font-size:.75rem;color:#64748b;margin-bottom:8px;display:flex;gap:12px}
  .card-desc{font-size:.82rem;color:#94a3b8;line-height:1.5;margin-bottom:14px}
  .btn{width:100%;padding:8px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:600;transition:opacity .2s}
  .btn-activate{background:#f59e0b;color:#000}.btn-activate:hover{opacity:.85}
  .btn-activate:disabled{background:#334155;color:#64748b;cursor:not-allowed}
  .btn-active{background:#713f12;color:#fde68a;cursor:default}
  .btn-loading{background:#1e3a8a;color:#93c5fd;cursor:wait}
  .btn-na{background:#1e293b;color:#64748b;cursor:not-allowed}

  .scan-section{margin-bottom:24px}
  .scan-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}
  .scan-title{font-size:.95rem;font-weight:600;color:#f1f5f9}
  .btn-scan{background:#1e293b;border:1px solid #334155;color:#94a3b8;padding:6px 14px;border-radius:8px;font-size:.8rem;cursor:pointer;transition:all .2s}
  .btn-scan:hover{border-color:#60a5fa;color:#60a5fa}
  .scan-dir{font-size:.75rem;color:#475569;font-family:monospace}
  .scan-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}
  .scan-card{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .scan-card.matched{border-color:#334155;opacity:.6}
  .scan-fname{font-size:.78rem;color:#e2e8f0;word-break:break-all;flex:1}
  .scan-size{font-size:.72rem;color:#64748b;flex-shrink:0;margin-right:8px}
  .scan-badge{font-size:.68rem;padding:2px 7px;border-radius:8px;background:#14532d;color:#86efac;flex-shrink:0}
  .btn-load{padding:5px 12px;border-radius:6px;border:none;background:#f59e0b;color:#000;font-size:.75rem;font-weight:600;cursor:pointer;flex-shrink:0}
  .btn-load:hover{opacity:.85}
  .btn-load:disabled{background:#334155;color:#64748b;cursor:not-allowed}
  .scan-empty{color:#475569;font-size:.82rem;padding:12px 0}
</style>
</head>
<body>
<h1>Qwen LLM 模型管理</h1>
<p class="sub">Frontend 整合：單一 API URL + API Key，切換模型無需修改前端設定</p>

<div class="info-bar">
  <div class="info-item">API URL <b id="info-url">—</b></div>
  <div class="info-item">認證 <b id="info-auth">—</b></div>
  <div class="info-item">端點 <code>POST /v1/chat/completions</code></div>
  <div class="info-item"><a href="/docs">/docs</a></div>
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

<div class="scan-section">
  <div class="scan-header">
    <span class="scan-title">掃描模型目錄</span>
    <button class="btn-scan" onclick="runScan()">🔍 掃描</button>
    <span class="scan-dir" id="scan-dir"></span>
  </div>
  <div class="scan-list" id="scan-list"><p class="scan-empty">點擊「掃描」列出目錄中所有 .gguf 檔案</p></div>
</div>

<script>
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) { console.error('[LLM] /api/status', res.status, await res.text()); return null; }
    const s = await res.json();
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    if (s.loading) {
      dot.className = 'dot loading';
      txt.textContent = '載入中：' + s.loading_id + '...';
    } else if (s.error) {
      dot.className = 'dot err';
      txt.textContent = '錯誤：' + s.error;
    } else if (s.active_name && s.server_alive) {
      dot.className = 'dot';
      txt.textContent = '運行中：' + s.active_name;
    } else if (s.active_name) {
      dot.className = 'dot err';
      txt.textContent = '進程異常：' + s.active_name;
    } else {
      dot.className = 'dot err';
      txt.textContent = '尚未載入模型';
    }
    if (s.vram && s.vram.total_gb > 0) {
      const pct = (s.vram.used_gb / s.vram.total_gb * 100).toFixed(0);
      document.getElementById('vram-fill').style.width = pct + '%';
      document.getElementById('vram-val').textContent = s.vram.used_gb + ' / ' + s.vram.total_gb + ' GB (' + pct + '%)';
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
      document.getElementById('ram-val').textContent = s.ram.used_gb + ' / ' + s.ram.total_gb + ' GB (' + s.ram.pct + '%)';
      document.getElementById('ram-sub').textContent = s.ram.pct > 85 ? '記憶體緊張' : '正常';
    }
    document.getElementById('info-url').textContent = location.origin;
    document.getElementById('info-auth').textContent = s.auth_enabled ? '已啟用（API Key）' : '未啟用';
    return s;
  } catch(e) { console.error('[LLM] fetchStatus error:', e); return null; }
}

async function renderGrid() {
  const [models] = await Promise.all([
    fetch('/api/models').then(r => r.json()).catch(() => []),
    fetchStatus(),
  ]);
  const grid = document.getElementById('model-grid');
  grid.innerHTML = models.map(m => {
    let btn;
    if (m.active)            btn = '<button class="btn btn-active" disabled>▶ 運行中</button>';
    else if (m.loading)      btn = '<button class="btn btn-loading" disabled>⏳ 載入中...</button>';
    else if (!m.available)   btn = '<button class="btn btn-na" disabled>⚠ 檔案不存在</button>';
    else                     btn = '<button class="btn btn-activate" onclick="activate(\\\'' + m.id + '\\\')">' + '啟用</button>';
    const avBadge = m.available ? '' : '<span class="badge badge-unavailable">未下載</span>';
    return '<div class="card' + (m.active?' active':'') + (m.loading?' loading-card':'') + (!m.available?' unavailable':'') + '">'
      + '<div class="card-name">' + m.name + '</div>'
      + '<div class="badges">'
      + (m.active  ? '<span class="badge badge-active">運行中</span>' : '')
      + (m.loading ? '<span class="badge badge-loading">載入中</span>' : '')
      + avBadge
      + '</div>'
      + '<div class="meta"><span>VRAM ≥ ' + m.vram + ' GB</span><span>' + m.size + '</span><span>ctx ' + (m.ctx/1024).toFixed(0) + 'k</span></div>'
      + '<div class="card-desc">' + m.desc + '</div>'
      + btn + '</div>';
  }).join('');
}

async function activate(id) {
  const r = await fetch('/api/models/' + id + '/activate', {method:'POST'});
  if (!r.ok) { const j = await r.json(); alert(j.detail || '切換失敗'); return; }
  renderGrid();
}

async function runScan() {
  document.getElementById('scan-list').innerHTML = '<p class="scan-empty">掃描中...</p>';
  try {
    const res = await fetch('/api/scan');
    const data = await res.json();
    document.getElementById('scan-dir').textContent = data.model_dir;
    if (!data.files || data.files.length === 0) {
      document.getElementById('scan-list').innerHTML = '<p class="scan-empty">目錄中沒有 .gguf 檔案</p>';
      return;
    }
    document.getElementById('scan-list').innerHTML = data.files.map(f => {
      const isMatched = !!f.matched_id;
      const badge = isMatched ? '<span class="scan-badge">已在清單</span>' : '';
      const btn = isMatched
        ? '<button class="btn-load" onclick="activate(\\\'' + f.matched_id + '\\\')">' + '啟用</button>'
        : '<button class="btn-load" onclick="loadFile(\\\'' + f.file + '\\\')">' + '載入</button>';
      return '<div class="scan-card' + (isMatched ? ' matched' : '') + '">'
        + '<span class="scan-fname">' + f.file + '</span>'
        + '<span class="scan-size">' + f.size + '</span>'
        + badge + btn + '</div>';
    }).join('');
  } catch(e) {
    document.getElementById('scan-list').innerHTML = '<p class="scan-empty">掃描失敗：' + e.message + '</p>';
  }
}

async function loadFile(fname) {
  const r = await fetch('/api/load-file', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({file: fname}),
  });
  if (!r.ok) { const j = await r.json(); alert(j.detail || '載入失敗'); return; }
  renderGrid();
  runScan();
}

renderGrid();
setInterval(renderGrid, 2000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    print(f"[LLM] Qwen LLM Manager — http://0.0.0.0:{PORT}/")
    print(f"[LLM] 預載模型：{DEFAULT_MODEL}")
    print(f"[LLM] 模型目錄：{MODEL_DIR}")
    print(f"[LLM] llama-server 內部 port：{LLAMA_PORT}")
    print(f"[LLM] 認證：{'已啟用' if AUTH_ENABLED else '未啟用（設定 API_KEY=sk-xxx 啟用）'}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
