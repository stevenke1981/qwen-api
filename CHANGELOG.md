# Changelog

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
