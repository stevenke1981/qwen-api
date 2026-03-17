# qwen-api

A local OpenAI-compatible API server for Qwen3.5-9B, powered by [llama.cpp](https://github.com/ggerganov/llama.cpp) with CUDA acceleration.

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
start.sh                      # Start the API server
frontend/serve.sh             # Start the chat UI (http://localhost:3000)
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

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

## Usage

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

A single-file chat frontend is included. In a second terminal:

```bash
bash frontend/serve.sh
```

Open `http://localhost:3000` in your browser.

Features:
- Streaming responses in real time
- Collapsible thinking blocks (`<think>...</think>`)
- Stop generation mid-stream
- Configurable API URL, model, temperature, max tokens, system prompt
- Online/Offline health indicator

## Optional: Python Bindings

`04_setup_project.sh` installs `llama-cpp-python` with CUDA for use in Python scripts:

```bash
bash 04_setup_project.sh
```

> Note: the current release of llama-cpp-python bundles an older llama.cpp that does not support the `qwen35` architecture. Use the native `llama-server` binary (built by `04b_build_llama_cpp.sh`) to serve the model.
