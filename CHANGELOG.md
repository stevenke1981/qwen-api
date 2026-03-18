# Changelog

## [Unreleased] — 2026-03-18

### Added
- `start_openclaw.sh` — llama-server optimised for OpenClaw/agent use: ctx 16384, n-predict 2048, no fetch proxy; defaults to `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M`, falls back to `.env` MODEL_PATH
- `06_convert_to_gguf.sh` — interactive script to download any HF model (safetensors) and convert to GGUF F16, then quantize to Q4_K_M / Q5_K_M / Q8_0 via `llama-quantize`
- `05_download_model.sh` — expanded to interactive menu with 5 model options including Qwen2.5-Coder variants and Uncensored HauhauCS model
- `tools.js: get_datetime` — browser-native date/time tool; model calls it instead of guessing date

### Changed
- `fetch_proxy.py /search` — `fetch_top` default changed `2 → 0` (auto page-fetch off by default to reduce context size); added `max_chars` param (default 1500)
- `chat.js streamCall()` — now captures `delta.reasoning_content` in addition to `delta.content` (some llama.cpp builds stream thinking here)
- `chat.js sendMessage()` — added fallback message when tools ran but model returned empty response
- `settings.js DEFAULTS` — system prompt updated: `get_datetime` does not replace `web_search`; rule against repeat searches
- `tools.js get_datetime` — description restricted to pure date/time queries to prevent misuse as search prerequisite
- `CLAUDE.md` — fully updated: new scripts, all tools, known issues, file tree

## [Unreleased] — 2026-03-18 (continued)

### Added
- `get_datetime` tool — model can now query current date/time from the browser (no network required)
- Export chat button — header button downloads full conversation as `chat-export-YYYY-MM-DD.md`
- Reset defaults button — settings panel restores temperature, system prompt, and all defaults
- Tool call log — persisted purple block at top of assistant bubble showing which tools ran (🔍🔗📄💾🕐)
- `settings.js: DEFAULTS` — hardcoded defaults object, single source of truth for all setting values
- `i18n.js: getLangInstruction()` — appends language reply instruction to system prompt on every send
- `i18n.js: resetSettings / export` — translation keys added to all 4 languages

### Changed
- `start.sh` — replaced `--tool-call-parser qwen` with `--jinja` (required by newer llama.cpp builds); removed `--chat-template chatml` which was overriding the model's built-in Jinja template
- `fetch_proxy.py /search` — switched DDGS call to `asyncio.to_thread()` to prevent blocking the async event loop; added 20s timeout; `fetch_top` default changed to `0` (off) to keep context size manageable
- `fetch_proxy.py /search` — added `max_chars` parameter (default 1500) controlling per-page text limit when `fetch_top > 0`
- `frontend/js/chat.js` — tool calling loop now captures `delta.reasoning_content` in addition to `delta.content` (compatibility with some llama.cpp streaming builds)
- `frontend/js/chat.js` — added fallback message when tools ran but model returned empty response
- `frontend/js/settings.js` — refined default system prompt: search-first rules, no repeat search, cite URLs, `get_datetime` does not replace `web_search`
- `frontend/js/tools.js` — `get_datetime` description restricted to pure date/time queries only
- `frontend/js/webfetch.js` — added `console.debug` logging for proxy calls (aids debugging)
- Temperature default: `0.7` → `0.1`

### Fixed
- Buttons (Think/Settings/Clear) disappeared after JS module load failure — root cause was browser cache; resolved with hard refresh (Ctrl+Shift+R)
- Tool call log showing `get_datetime: get_datetime` — fixed `logDetail` to show actual current timestamp
- Model responded with training data instead of searching — fixed via system prompt rules and `get_datetime` tool description guard

## [Unreleased]

### Added
- `build_essential.sh` — installs cmake, gcc, ninja-build, and other compile tools
- `CACHE_TYPE_K` / `CACHE_TYPE_V` env vars — KV cache quantization (default `q8_0`)
- `N_UBATCH` env var — micro-batch size for better GPU utilization

### Performance
- Increased default `N_CTX` from 8192 → 32768 (4× more context, fits in VRAM with q8_0 KV cache)
- Added `--cache-type-k q8_0` and `--cache-type-v q8_0` — halves KV cache VRAM usage
- Added `--ubatch-size 512` — improves GPU throughput during prompt processing
- Added `--defrag-thold 0.1` — automatic KV cache defragmentation for long conversations
- `04b_build_llama_cpp.sh` — builds llama.cpp C++ binaries (llama-server, llama-cli, llama-bench, llama-quantize) from source with CUDA support
- `frontend/index.html` — single-file chat UI with streaming, collapsible thinking blocks, stop button, and settings panel
- `frontend/serve.sh` — serves the frontend via Python's built-in HTTP server (`bash frontend/serve.sh`)

### Changed
- `start.sh` — switched from Python `llama-cpp-python` server to native `llama-server` binary; fixes `unknown model architecture: qwen35` error caused by outdated bundled llama.cpp in the Python bindings
- `04_setup_project.sh` — rewritten to install all Python deps in a single `uv pip install` call, preventing `uv sync` from removing llama-cpp-python
- `README.md` — updated with full workflow overview and corrected setup steps

### Fixed
- Model fails to load with `ValueError: Failed to load model from file` due to `qwen35` architecture not supported in llama-cpp-python's bundled llama.cpp — resolved by switching to native llama-server

## [0.1.0] — 2026-03-17

### Added
- Initial release
- `01_install_nvidia_driver.sh` — NVIDIA driver installation
- `02_install_cuda.sh` — CUDA toolkit installation
- `03_install_python.sh` — Python 3.12 installation via uv
- `04_setup_project.sh` — Python project dependencies with llama-cpp-python (CUDA, from git)
- `05_download_model.sh` — Qwen3.5-9B Q5_K_M GGUF download from Hugging Face
- `start.sh` — API server startup script
- `main.py` — llama-cpp-python OpenAI-compatible server
- `.env.example` — configuration template
