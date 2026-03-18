# Scripts Flowchart

## 安裝流程

```mermaid
flowchart TD
    START([開始 / 新機器]) --> TW

    TW["setup_tw_mirror.sh\n加入台灣 apt 鏡像站（選用）"]
    TW --> DRV

    DRV["01_install_nvidia_driver.sh\n安裝 NVIDIA 驅動"]
    DRV --> REBOOT["🔁 重新開機"]
    REBOOT --> CUDA

    CUDA["02_install_cuda.sh\n安裝 CUDA Toolkit"]
    CUDA --> BUILD

    BUILD["build_essential.sh\ncmake / gcc / ninja 等編譯工具"]
    BUILD --> PY

    PY["03_install_python.sh\n安裝 Python 3.12 via uv\n建立 .venv"]
    PY --> LLAMA

    LLAMA["04b_build_llama_cpp.sh\n從原始碼編譯 llama-server\n產出：~/.local/bin/llama-server"]
    LLAMA --> MODEL

    MODEL{"模型取得方式"}

    MODEL -->|"下載現成 GGUF"| DL["05_download_model.sh\n互動選單 5 種模型\n1 Qwen3.5-9B Q5_K_M\n2 Qwen2.5-Coder-7B Q8\n3 Qwen2.5-Coder-14B Q4\n4 Qwen2.5-Coder-14B Q8\n5 Qwen3.5-9B Uncensored Q4"]
    MODEL -->|"從 HuggingFace 自行轉換"| CONV["06_convert_to_gguf.sh\nHF safetensors → GGUF F16\n再量化 Q4_K_M / Q5_K_M / Q8_0"]

    DL --> RUN
    CONV --> RUN

    RUN{"啟動用途"}

    RUN -->|"聊天前端"| START_CHAT["start.sh\nllama-server :8000\nfetch_proxy.py :8001"]
    RUN -->|"OpenClaw Agent"| START_OC["start_openclaw.sh\nllama-server :8000\nctx=16384 / n-predict=2048\n預設 Uncensored 模型"]

    START_CHAT --> FE["frontend/serve.sh\nfrontend/start_frontend.bat\nhttp://localhost:3000"]
    START_OC --> OC["OpenClaw\nAPI Base: http://server:8000\nModel: qwen"]
```

---

## 選用腳本

```mermaid
flowchart LR
    OPT1["04_setup_project.sh\n⚠ 已棄用\nPython llama-cpp-python 綁定\n僅在 Python 程式直接呼叫模型時需要"]

    OPT2["07_setup_remote_desktop.sh\nXFCE4 + XRDP\nWindows 遠端桌面 :3389"]

    OPT3["setup_tw_mirror.sh\n台灣 apt 鏡像\nNCTU / NTU / HiNet"]
```

---

## 腳本一覽

| 腳本 | 功能 | 必要 |
|------|------|------|
| `setup_tw_mirror.sh` | 加入台灣 apt 鏡像（NCTU / NTU / HiNet） | 選用 |
| `01_install_nvidia_driver.sh` | 安裝 NVIDIA 驅動 → 需重開機 | ✅ |
| `02_install_cuda.sh` | 安裝 CUDA Toolkit | ✅ |
| `build_essential.sh` | 安裝 cmake、gcc 等編譯工具 | ✅ |
| `03_install_python.sh` | 安裝 Python 3.12 via uv、建立 `.venv` | ✅ |
| `04_setup_project.sh` | Python llama-cpp-python 綁定 ⚠ 已棄用 | 選用 |
| `04b_build_llama_cpp.sh` | 從原始碼編譯 llama-server（CUDA） | ✅ |
| `05_download_model.sh` | 下載現成 GGUF 模型（5 選項） | ✅ |
| `06_convert_to_gguf.sh` | HF safetensors → GGUF + 量化 | 選用 |
| `07_setup_remote_desktop.sh` | XFCE4 + XRDP 遠端桌面 | 選用 |
| `start.sh` | 啟動聊天 API（port 8000 + 8001） | 執行時 |
| `start_openclaw.sh` | 啟動 OpenClaw 專用 API（port 8000） | 執行時 |
| `frontend/serve.sh` | 啟動聊天前端（port 3000，Linux） | 執行時 |
| `frontend/start_frontend.bat` | 啟動聊天前端（port 3000，Windows） | 執行時 |
