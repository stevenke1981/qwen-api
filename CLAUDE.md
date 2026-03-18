# CLAUDE.md — Project Context for Claude Code

This file exists so any Claude Code session can immediately understand the project state and continue work without re-discovery.

---

## Project Summary

A **local OpenAI-compatible LLM server** running Qwen3.5-9B via llama.cpp (CUDA), plus a **full-featured chat frontend** with tool calling (web search, web fetch, get_datetime, file read/write, export).

- **Backend**: `llama-server` (llama.cpp native binary, port 8000) + `fetch_proxy.py` (FastAPI, port 8001)
- **Frontend**: Pure ES Modules, no bundler — served via `python -m http.server 3000`
- **Platform**: Ubuntu 24.04 server (NVIDIA RTX 3060 12 GB), frontend accessed from Windows browser via LAN

---

## How to Run

```bash
# Chat frontend + web tools
bash start.sh                 # llama-server (port 8000) + fetch_proxy (port 8001)

# OpenClaw / coding agent (optimised)
bash start_openclaw.sh        # ctx 16384, n-predict 2048, no fetch proxy

# Frontend (Linux or Windows)
bash frontend/serve.sh        # Linux/macOS → http://localhost:3000
frontend\start_frontend.bat   # Windows    → http://localhost:3000
```

---

## Architecture

```
Browser (port 3000)
  ├── frontend/index.html          HTML shell
  ├── frontend/css/style.css       All styles
  └── frontend/js/
        ├── chat.js                Main orchestrator (tool-calling loop, streaming)
        ├── i18n.js                Translations (EN/繁中/简中/日本語)
        ├── settings.js            localStorage persistence + DEFAULTS + resetSettings
        ├── health.js              /health polling (10s interval)
        ├── render.js              Message rendering (code blocks, think blocks, quote)
        ├── tools.js               TOOLS definition + executeTool() dispatcher
        └── webfetch.js            fetchPageText() / searchWeb() via proxy

Linux Server
  ├── start.sh                     Launches llama-server + fetch_proxy
  ├── start_openclaw.sh            Launches llama-server (agent-optimised, no proxy)
  ├── fetch_proxy.py               FastAPI proxy (CORS bypass)
  │     POST /fetch                → fetch URL, strip HTML, return plain text
  │     POST /search               → DuckDuckGo search (asyncio.to_thread) + optional auto-fetch
  └── llama-server                 OpenAI-compatible API (llama.cpp, built from source)
        POST /v1/chat/completions  streaming, tool_calls via --jinja
```

---

## Tool Calling Flow

```
User sends message
  → chat.js sends to /v1/chat/completions with TOOLS array + tool_choice:'auto'
  → if finish_reason === "tool_calls":
      → executeTool() called for each tool
      → result pushed as role:"tool" message
      → loop continues (model sees tool result, answers)
  → final text rendered in bubble
  → tool log shown at top of bubble (🔍/🔗/🕐/📄/💾)
  → if finalText empty after tools ran → fallback message shown
```

### Available Tools

| Tool | What it does |
|------|-------------|
| `web_search` | DuckDuckGo search; `fetch_top=0` by default (summary only) |
| `web_fetch` | Fetches a URL via proxy, returns stripped plain text |
| `get_datetime` | Returns current date/time from browser (no network needed) |
| `read_file` | Opens browser file picker, reads text content |
| `write_file` | Creates Blob download in browser |

---

## Key Files — What's in Each

### `start.sh`
- Loads `.env` config
- Installs fetch proxy deps into `.venv` via `uv pip install` if missing
- Starts `.venv/bin/python3 fetch_proxy.py 8001` in background (trap for cleanup)
- Runs `llama-server` with: `--flash-attn on`, `--jinja`, `--cache-type-k/v q8_0`, `--ctx-size 32768`, `--batch-size 1024`
- **Tool calling** enabled via `--jinja` (Jinja template engine, replaces old `--tool-call-parser`)

### `start_openclaw.sh`
- Uses `OPENCLAW_MODEL_PATH` env var, defaults to `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf`
- Falls back to `.env` `MODEL_PATH` if Uncensored model not found
- `--ctx-size 16384` (saves VRAM), `--n-predict 2048` (faster agent responses)
- No fetch proxy (OpenClaw has its own tools)

### `fetch_proxy.py`
- FastAPI with CORS `allow_origins=["*"]`
- `/fetch`: streams URL, BeautifulSoup strip, returns `{url, title, text, truncated, total_chars}`
- `/search`: runs `DDGS().text()` via `asyncio.to_thread()` with 20s timeout; `fetch_top=0` default (off); `max_chars=1500` per page when fetch_top>0
- Debug prints at each step (`[search] ...`) — visible in terminal

### `frontend/js/chat.js`
- `streamCall()`: streams SSE, accumulates `tool_calls` delta chunks by index; captures both `delta.content` and `delta.reasoning_content`
- `sendMessage()`: tool-calling while-loop, builds `toolLogHtml`, appends lang instruction to system prompt
- Fallback: if tools ran but `finalText` is empty → shows `*(No response generated after tool execution)*`
- Export button: converts `history[]` to markdown, triggers Blob download
- Reset button: calls `resetSettings()`, clears localStorage

### `frontend/js/settings.js`
- `DEFAULTS`: hardcoded defaults — temperature 0.1, search-first system prompt with rules:
  - Search before answering anything potentially outdated
  - `get_datetime` does NOT replace `web_search`
  - No repeat searches; cite URLs
- `loadSettings()` / `resetSettings()` / `saveSettings()`

### `frontend/js/i18n.js`
- `TRANSLATIONS`: EN / zh-TW / zh-CN / ja — all keys must exist in all 4 langs
- `getLangInstruction()`: returns system prompt suffix in current UI language
- `detectLang()`: matches `navigator.languages` to supported langs

### `frontend/js/tools.js`
- `TOOLS`: 5 tools — `web_search`, `web_fetch`, `get_datetime`, `read_file`, `write_file`
- `get_datetime`: restricted description — only for pure date/time queries, not as pre-search step
- `executeTool()`: routes by name → proxy calls or browser File API

### `05_download_model.sh`
- Interactive menu: 5 model options
  1. Qwen3.5-9B Q5_K_M (default chat)
  2. Qwen2.5-Coder-7B Q8_0
  3. Qwen2.5-Coder-14B Q4_K_M
  4. Qwen2.5-Coder-14B Q8_0
  5. Qwen3.5-9B Uncensored HauhauCS Q4_K_M (OpenClaw default)

### `06_convert_to_gguf.sh`
- Downloads any HF model (default: `Qwen/Qwen3.5-9B`) as safetensors
- Converts to GGUF F16 via `~/llama.cpp/convert_hf_to_gguf.py`
- Quantizes to Q4_K_M / Q5_K_M / Q8_0 / all (interactive)
- Override: `HF_REPO=... MODEL_NAME=... bash 06_convert_to_gguf.sh`

---

## Configuration (`.env`)

```env
MODEL_PATH=/home/steven/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf
HOST=0.0.0.0
PORT=8000
N_GPU_LAYERS=-1
N_CTX=32768
N_BATCH=1024
N_UBATCH=512
CACHE_TYPE_K=q8_0
CACHE_TYPE_V=q8_0
```

---

## Frontend Settings Defaults

| Setting | Default |
|---------|---------|
| API Server | `http://192.168.80.60:8000` |
| Model | `qwen` |
| Max Tokens | `6144` |
| Temperature | `0.1` |
| System Prompt | Search-first rules — search before answering, specific queries, no repeat search, cite URLs, `get_datetime` ≠ `web_search` |

---

## Known Issues / Pending

### Tool calling — how it works now
- `--tool-call-parser` was removed from newer llama.cpp
- Tool calling now works via `--jinja` (Jinja template engine)
- Removing `--chat-template chatml` was required — it overrode the model's built-in Jinja template
- Verify: DevTools → Network → `chat/completions` → `finish_reason: "tool_calls"` ✅

### If tool calling stops working after rebuild
```bash
llama-server --help | grep jinja
# Should show --jinja, --no-jinja
# If missing: bash 04b_build_llama_cpp.sh
```

### If model has no/wrong Jinja template (fine-tuned models)
```bash
# Force built-in Qwen3 template in start_openclaw.sh:
--jinja \
--chat-template qwen3
```

### fetch_proxy.py dependencies
- Must use `.venv/bin/python3` (not system `python3`)
- Deps: `httpx beautifulsoup4 fastapi[standard] duckduckgo-search uvicorn`

### Debug logging (temporary — remove when stable)
- `fetch_proxy.py`: `[search] ...` prints to terminal
- `frontend/js/webfetch.js`: `console.debug('[searchWeb] ...')`

### Model empty response after tool call
- Root cause: model outputs only `<think>` content, no answer text
- Fix applied: `delta.reasoning_content` also captured; fallback message shown if empty

---

## UI Features

| Feature | Where |
|---------|-------|
| Multilingual | Header `<select>` → EN/繁中/简中/日本語, auto-detect from browser |
| Language-matched replies | `getLangInstruction()` appended to system prompt on each send |
| Thinking mode | Header toggle (`Think: ON/OFF`), prepends `/think` or `/no_think` |
| Tool status | Pulsing card in bubble during tool execution |
| Tool call log | Persisted at top of bubble (🔍🔗🕐📄💾) |
| Quote messages | Hover → Quote button; select text for partial quote |
| Export chat | Header Export → `chat-export-YYYY-MM-DD.md` |
| Reset settings | Settings panel → Reset defaults button |
| Health indicator | Header dot (green/red), polls every 10s |
| Code blocks | Syntax highlighted, copy button |
| Streaming | Real-time token display with blinking cursor |

---

## File Tree

```
qwen-api/
├── CLAUDE.md                  ← this file
├── README.md
├── CHANGELOG.md
├── HOW1.md                    performance tuning notes
├── start.sh                   chat server startup (port 8000 + 8001)
├── start_openclaw.sh          agent-optimised server (port 8000, no proxy)
├── fetch_proxy.py             CORS proxy + DuckDuckGo search
├── .env / .env.example
├── build_essential.sh
├── 01_install_nvidia_driver.sh
├── 02_install_cuda.sh
├── 03_install_python.sh
├── 04_setup_project.sh        (optional Python bindings)
├── 04b_build_llama_cpp.sh     build llama-server from source
├── 05_download_model.sh       download pre-quantized GGUF (5 models)
├── 06_convert_to_gguf.sh      HF safetensors → GGUF + quantize
└── frontend/
    ├── index.html
    ├── serve.sh
    ├── start_frontend.bat
    ├── css/style.css
    └── js/
        ├── chat.js
        ├── i18n.js
        ├── settings.js
        ├── health.js
        ├── render.js
        ├── tools.js
        └── webfetch.js
```
