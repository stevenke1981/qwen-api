# CLAUDE.md — Project Context for Claude Code

This file exists so any Claude Code session can immediately understand the project state and continue work without re-discovery.

---

## Project Summary

A **local OpenAI-compatible LLM server** running Qwen3.5-9B via llama.cpp (CUDA), plus a **full-featured chat frontend** with tool calling (web search, web fetch, file read/write, export).

- **Backend**: `llama-server` (llama.cpp native binary, port 8000) + `fetch_proxy.py` (FastAPI, port 8001)
- **Frontend**: Pure ES Modules, no bundler — served via `python -m http.server 3000`
- **Platform**: Ubuntu 24.04 server (NVIDIA RTX 3060 12 GB), frontend accessed from Windows browser

---

## How to Run

```bash
# On Linux server
bash start.sh            # starts llama-server (port 8000) + fetch_proxy (port 8001)

# On Windows client (or Linux)
frontend\start_frontend.bat   # Windows
bash frontend/serve.sh        # Linux/macOS
# then open http://localhost:3000
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
  │     POST /search               → DuckDuckGo search + auto-fetch top 2 pages
  └── llama-server                 OpenAI-compatible API (llama.cpp)
        POST /v1/chat/completions  streaming, tool_calls support
```

---

## Tool Calling Flow

```
User sends message
  → chat.js sends to /v1/chat/completions with TOOLS array
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
- Starts `fetch_proxy.py` in background (trap for cleanup)
- Runs `llama-server` with: `--flash-attn`, `--cache-type-k/v q8_0`, `--ctx-size 32768`, `--batch-size 1024`
- **Requires** `--tool-call-parser qwen` (already added) for tool calling to work

### `fetch_proxy.py`
- FastAPI with CORS `allow_origins=["*"]`
- `/fetch`: streams URL, BeautifulSoup strip, returns `{url, title, text, truncated, total_chars}`
- `/search`: DDGS().text() + parallel `_fetch_text()` for top N results → returns `full_text` field

### `frontend/js/chat.js`
- `streamCall()`: streams SSE, accumulates `tool_calls` delta chunks by index
- `sendMessage()`: tool-calling while-loop, builds `toolLogHtml`, appends lang instruction to system prompt
- Export button: converts `history[]` to markdown, triggers Blob download
- Reset button: calls `resetSettings()`, clears localStorage

### `frontend/js/settings.js`
- `DEFAULTS`: hardcoded defaults (temperature=0.1, system prompt with search rules)
- `loadSettings()`: fills form from localStorage
- `resetSettings()`: clears localStorage, restores DEFAULTS
- `saveSettings(thinking)`: persists all form values

### `frontend/js/i18n.js`
- `TRANSLATIONS`: EN / zh-TW / zh-CN / ja — all keys must exist in all 4 langs
- `getLangInstruction()`: returns system prompt suffix in current UI language
- `detectLang()`: matches `navigator.languages` to supported langs

### `frontend/js/render.js`
- `renderContent(bubble, text, streaming, showThinking)`: parses fenced code blocks + `<think>` blocks
- Code blocks: syntax-highlighted header, one-click copy, fallback execCommand
- Think blocks: collapsed by default, click to expand

### `frontend/js/tools.js`
- `TOOLS`: OpenAI function calling format definitions
- `executeTool()`: routes by name → calls webfetch.js helpers or browser File API
- `readFileFromUser()`: `<input type=file>` promise, handles cancel event
- `writeFileToUser()`: Blob URL + `<a download>` click

---

## Configuration (`.env`)

```env
MODEL_PATH=~/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf
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
| System Prompt | Search-first rules (see DEFAULTS in settings.js) |

---

## Known Issues / Pending

### Tool calling not working
**Symptom**: Model says "I cannot browse the web" instead of calling `web_search`.
**Cause**: `--tool-call-parser` flag — must restart `start.sh` after adding it.
**Fix already applied** in `start.sh`: `--tool-call-parser qwen`
**Verify**: Open DevTools → Network → `chat/completions` response → check `finish_reason`
- `"tool_calls"` = working ✅
- `"stop"` = parser not recognizing tool calls ❌ (try `--tool-call-parser generic`)

### If `--tool-call-parser` flag not recognized
Your llama-server version may be too old. Check:
```bash
llama-server --help | grep tool-call-parser
llama-server --version
```
Rebuild from source: `bash 04b_build_llama_cpp.sh`

---

## UI Features

| Feature | Where |
|---------|-------|
| Multilingual | Header `<select>` → EN/繁中/简中/日本語, auto-detect from browser |
| Language-matched replies | `getLangInstruction()` appended to system prompt on each send |
| Thinking mode | Header toggle, prepends `/think` or `/no_think` to user message |
| Quote messages | Hover message → Quote button; select text for partial quote |
| Export chat | Header Export button → downloads `chat-export-YYYY-MM-DD.md` |
| Reset settings | Settings panel → Reset defaults button |
| Tool call log | Shown at top of assistant bubble after response (🔍🔗📄💾) |
| Health indicator | Header dot (green=online, red=offline), polls every 10s |
| Code blocks | Syntax highlighted, copy button with `copied!` feedback |
| Streaming | Real-time token display with blinking cursor |

---

## File Tree

```
qwen-api/
├── CLAUDE.md                  ← this file
├── README.md
├── HOW1.md                    performance tuning notes
├── HOW2.md                    (未使用)
├── start.sh                   server startup
├── fetch_proxy.py             CORS proxy + search
├── .env.example
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
