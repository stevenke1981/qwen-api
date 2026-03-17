# qwen-api

A local OpenAI-compatible API server for Qwen3.5-9B, powered by [llama.cpp](https://github.com/ggerganov/llama.cpp) with CUDA acceleration, plus a full-featured chat frontend with tool calling support.

## Requirements

- Ubuntu (tested on 24.04)
- NVIDIA GPU with CUDA support (tested on RTX 3060 12 GB)
- ~7 GB disk space for the model

## Workflow

```
01_install_nvidia_driver.sh   # Install NVIDIA driver → reboot
02_install_cuda.sh            # Install CUDA toolkit
build_essential.sh            # Install cmake, gcc, build tools
03_install_python.sh          # Install Python 3.12 via uv
04b_build_llama_cpp.sh        # Build llama.cpp binaries with CUDA
05_download_model.sh          # Download Qwen3.5-9B GGUF (~6.86 GB)
start.sh                      # Start API server + fetch proxy
frontend/serve.sh             # Start the chat UI  (Linux)
frontend/start_frontend.bat   # Start the chat UI  (Windows)
```

> `04_setup_project.sh` installs the Python bindings (llama-cpp-python) and is optional — the server runs via the native `llama-server` binary.

## Setup

### 1. Install NVIDIA Driver

```bash
bash 01_install_nvidia_driver.sh
# Reboot after this step
```

### 2. Install CUDA

```bash
bash 02_install_cuda.sh
```

### 3. Install Build Tools

```bash
bash build_essential.sh
```

### 4. Install Python (via uv)

```bash
bash 03_install_python.sh
```

### 5. Build llama.cpp Binaries

Compiles `llama-server`, `llama-cli`, `llama-bench`, and `llama-quantize` from source with CUDA support. Installs to `~/.local/bin`.

```bash
bash 04b_build_llama_cpp.sh
```

### 6. Download Model

Downloads `Qwen_Qwen3.5-9B-Q5_K_M.gguf` (~6.86 GB) from Hugging Face.

```bash
bash 05_download_model.sh
```

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `MODEL_PATH` | `~/models/Qwen_Qwen3.5-9B-Q5_K_M.gguf` | Path to the GGUF model file |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `N_GPU_LAYERS` | `-1` | GPU layers (`-1` = all) |
| `N_CTX` | `32768` | Context window size |
| `N_BATCH` | `1024` | Batch size (prompt processing) |
| `N_UBATCH` | `512` | Micro-batch size (GPU utilization) |
| `CACHE_TYPE_K` | `q8_0` | KV cache quantization for K (saves VRAM) |
| `CACHE_TYPE_V` | `q8_0` | KV cache quantization for V (saves VRAM) |

## Start

```bash
bash start.sh
```

`start.sh` launches two services:

| Service | Port | Description |
|---------|------|-------------|
| llama-server | 8000 | OpenAI-compatible LLM API |
| fetch_proxy.py | 8001 | Web fetch / search proxy (CORS bypass) |

The LLM API is available at `http://<host>:8000`.

## API Usage

The server exposes an OpenAI-compatible API. Example with `curl`:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

Or point any OpenAI-compatible client at `http://localhost:8000`.

## Chat UI

A modular chat frontend is included (`frontend/`).

**Linux / macOS:**
```bash
bash frontend/serve.sh
```

**Windows:**
```bat
frontend\start_frontend.bat
```

Open `http://localhost:3000` in your browser.

### Frontend Features

| Feature | Description |
|---------|-------------|
| Streaming responses | Real-time token streaming with blinking cursor |
| Thinking mode toggle | Header button — prepends `/think` or `/no_think` per message |
| Collapsible thinking blocks | `<think>` blocks rendered and collapsed by default |
| Tool calling | Model autonomously calls web_search / web_fetch / read_file / write_file |
| Tool call log | 🔍🔗📄💾 shown at top of bubble after response |
| Quote messages | Hover → Quote button; select text for partial quote |
| Code blocks | Syntax-highlighted with one-click copy |
| Export chat | Downloads conversation as Markdown |
| Multilingual UI | EN / 繁中 / 简中 / 日本語 (auto-detects browser language) |
| Language-matched replies | UI language instruction appended to system prompt automatically |
| Configurable settings | API server, model, temperature, max tokens, system prompt |
| Reset settings | Restore all defaults in one click |
| Settings persistence | All settings saved to localStorage |
| Health indicator | Online / Offline dot, polls every 10s |

### Tool Calling (MCP-style)

The model autonomously decides when to use tools. No special syntax required — just ask naturally.

| Tool | Example prompt | Action |
|------|---------------|--------|
| `web_fetch` | "Read github.com/openai" | Fetches and returns page text |
| `web_search` | "Search for Qwen3 latest news" | DuckDuckGo search results |
| `read_file` | "Analyse this file for me" | Opens file picker → reads content |
| `write_file` | "Save this report as report.txt" | Downloads file to your computer |

URL format is flexible — `example.com`, `www.site.com`, and `https://example.com` all work.

**Tool call flow:**
```
User message → model requests tool → frontend executes → result returned → model answers
```

### LAN Access

Set **API Server** in Settings to your server's LAN IP (e.g. `http://192.168.80.60:8000`).
The fetch proxy is automatically derived from the same host on port `8001`.

## Performance Notes

See `HOW1.md` for detailed tuning guidance.

Key settings already applied:
- `--flash-attn on` — reduces prefill memory access
- `--jinja` — enables Jinja template engine for tool calling support
- `N_BATCH=1024` — higher prefill throughput
- `N_CTX=32768` — 32K context window
- `CACHE_TYPE_K/V=q8_0` — quantized KV cache (saves ~40% VRAM)

> Rebuild `llama-server` from source with `bash 04b_build_llama_cpp.sh` to ensure the latest llama.cpp features (Jinja tool calling, qwen35 architecture support).

## Optional: Python Bindings

`04_setup_project.sh` installs `llama-cpp-python` with CUDA for use in Python scripts:

```bash
bash 04_setup_project.sh
```

> Note: the current release of llama-cpp-python bundles an older llama.cpp that does not support the `qwen35` architecture. Use the native `llama-server` binary (built by `04b_build_llama_cpp.sh`) to serve the model.
