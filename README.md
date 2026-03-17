# qwen-api

A local OpenAI-compatible API server for Qwen3.5-9B, powered by [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) with CUDA acceleration.

## Requirements

- Ubuntu (tested on 24.04)
- NVIDIA GPU with CUDA support
- ~7 GB disk space for the model

## Setup

Run the numbered scripts in order. Each script is idempotent and will skip steps already completed.

### 1. Install NVIDIA Driver

```bash
bash 01_install_nvidia_driver.sh
# Reboot after this step
```

### 2. Install CUDA

```bash
bash 02_install_cuda.sh
```

### 3. Install Python (via uv)

```bash
bash 03_install_python.sh
```

### 4. Install Python Dependencies

Compiles `llama-cpp-python` from source with CUDA support — this takes a few minutes.

```bash
bash 04_setup_project.sh
```

### 4b. Build llama.cpp Binaries (optional)

Builds the llama.cpp C++ binaries (`llama-cli`, `llama-server`, `llama-bench`, `llama-quantize`) and installs them to `~/.local/bin`. Only needed if you want to use the CLI tools directly.

```bash
bash 04b_build_llama_cpp.sh
```

### 5. Download Model

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
| `N_CTX` | `8192` | Context window size |
| `N_BATCH` | `512` | Batch size |

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
