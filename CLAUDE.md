# CLAUDE.md — Project Context for Claude Code

This file exists so any Claude Code session can immediately understand the project state and continue work without re-discovery.

---

## Project Summary

A **local OpenAI-compatible LLM server** running Qwen3.5-9B via llama.cpp (CUDA), plus a **full-featured chat frontend** with tool calling (web search, web fetch, file read/write, export).

- **Backend**: `llama-server` (llama.cpp native binary, port 8000) + `fetch_proxy.py` (FastAPI, port 8001)
- **Frontend**: Pure ES Modules, no bundler — served via `python -m http.server 3000`
- **Platform**: Ubuntu 24.04 server (NVIDIA RTX 3060 12 GB), frontend accessed from Windows browser via LAN

---

## How to Run

```bash
# On Linux server
bash start.sh                 # starts llama-server (port 8000) + fetch_proxy (port 8001)

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
  ├── fetch_proxy.py               FastAPI proxy (CORS bypass)
  │     POST /fetch                → fetch URL, strip HTML, return plain text
  │     POST /search               → DuckDuckGo search (asyncio.to_thread) + auto-fetch top 2 pages
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
  → tool log shown at top of bubble (🔍/🔗/📄/💾)
```

### Available Tools

| Tool | What it does |
|------|-------------|
| `web_search` | DuckDuckGo search, auto-fetches top 2 results' full text |
| `web_fetch` | Fetches a URL via proxy, returns stripped plain text |
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

### `fetch_proxy.py`
- FastAPI with CORS `allow_origins=["*"]`
- `/fetch`: streams URL, BeautifulSoup strip, returns `{url, title, text, truncated, total_chars}`
- `/search`: runs `DDGS().text()` via `asyncio.to_thread()` with 20s timeout (non-blocking), parallel `_fetch_text()` for top N results
- Debug prints at each step (`[search] ...`) — visible in `start.sh` terminal

### `frontend/js/chat.js`
- `streamCall()`: streams SSE, accumulates `tool_calls` delta chunks by index
- `sendMessage()`: tool-calling while-loop with round/debug logging, builds `toolLogHtml`, appends lang instruction to system prompt
- `showToolInBubble(bubble, statusMsg)`: shows pulsing card with correct emoji (🔍/🔗) during tool execution
- Export button: converts `history[]` to markdown, triggers Blob download
- Reset button: calls `resetSettings()`, clears localStorage

### `frontend/js/settings.js`
- `DEFAULTS`: hardcoded defaults including refined system prompt with search rules
- `loadSettings()`: fills form from localStorage, returns `{ lang, thinking }`
- `resetSettings()`: clears localStorage, restores DEFAULTS
- `saveSettings(thinking)`: persists all form values; `thinking` param is optional (reads prev value if omitted)

### `frontend/js/i18n.js`
- `TRANSLATIONS`: EN / zh-TW / zh-CN / ja — all keys must exist in all 4 langs
- `getLangInstruction()`: returns system prompt suffix in current UI language
- `detectLang()`: matches `navigator.languages` to supported langs

### `frontend/js/render.js`
- `renderContent(bubble, text, streaming, showThinking)`: parses fenced code blocks + `<think>` blocks
- Code blocks: syntax-highlighted header, one-click copy
- Think blocks: collapsed by default, click to expand

### `frontend/js/tools.js`
- `TOOLS`: OpenAI function calling format definitions
- `executeTool()`: routes by name → calls webfetch.js helpers or browser File API
- `readFileFromUser()`: `<input type=file>` promise, handles cancel event
- `writeFileToUser()`: Blob URL + `<a download>` click

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
| System Prompt | Search-first rules — search before answering, specific queries, no repeat search, cite URLs |

---

## Known Issues / Pending

### Tool calling — how it works now
- `--tool-call-parser` was removed from newer llama.cpp
- Tool calling now works via `--jinja` (Jinja template engine, enabled by default)
- Removing `--chat-template chatml` was required — it was overriding the model's built-in Jinja template
- Verify tool calling: DevTools → Network → `chat/completions` → check `finish_reason: "tool_calls"`

### If tool calling stops working after rebuild
```bash
llama-server --help | grep jinja
```
Should show `--jinja, --no-jinja`. If missing, rebuild: `bash 04b_build_llama_cpp.sh`

### fetch_proxy.py dependencies
- Must use `.venv/bin/python3` to run (not system `python3`)
- `uv pip install` puts packages in `.venv`, not system Python
- Deps: `httpx beautifulsoup4 fastapi[standard] duckduckgo-search uvicorn`

### Debug logging (temporary)
- `fetch_proxy.py`: prints `[search] ...` steps to terminal — remove when stable
- `frontend/js/chat.js`: `console.debug('[tool-loop] ...')` — remove when stable
- `frontend/js/webfetch.js`: `console.debug('[searchWeb] ...')` — remove when stable

---

## UI Features

| Feature | Where |
|---------|-------|
| Multilingual | Header `<select>` → EN/繁中/简中/日本語, auto-detect from browser |
| Language-matched replies | `getLangInstruction()` appended to system prompt on each send |
| Thinking mode | Header toggle (`Think: ON/OFF`), prepends `/think` or `/no_think` to user message |
| Tool status | Pulsing card in bubble during tool execution (🔍 Searching / 🔗 Fetching) |
| Tool call log | Shown at top of bubble after response (🔍🔗📄💾) |
| Quote messages | Hover message → Quote button; select text for partial quote |
| Export chat | Header Export button → downloads `chat-export-YYYY-MM-DD.md` |
| Reset settings | Settings panel → Reset defaults button |
| Health indicator | Header dot (green=online, red=offline), polls every 10s |
| Code blocks | Syntax highlighted, copy button with `copied!` feedback |
| Streaming | Real-time token display with blinking cursor |

---

## File Tree

```
qwen-api/
├── CLAUDE.md                  ← this file
├── README.md
├── CHANGELOG.md
├── HOW1.md                    performance tuning notes
├── HOW2.md
├── start.sh                   server startup
├── fetch_proxy.py             CORS proxy + search
├── .env / .env.example
├── build_essential.sh         install cmake/gcc
├── 01_install_nvidia_driver.sh
├── 02_install_cuda.sh
├── 03_install_python.sh
├── 04_setup_project.sh        (optional Python bindings)
├── 04b_build_llama_cpp.sh     build llama-server from source
├── 05_download_model.sh
└── frontend/
    ├── index.html
    ├── serve.sh               Linux frontend server
    ├── start_frontend.bat     Windows frontend server
    ├── css/
    │   └── style.css
    └── js/
        ├── chat.js
        ├── i18n.js
        ├── settings.js
        ├── health.js
        ├── render.js
        ├── tools.js
        └── webfetch.js
```
