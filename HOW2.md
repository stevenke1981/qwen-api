# 讓模型能夠 Fetch 網站的實現方式

模型本身無法主動上網，只能處理給它的文字。要讓模型取得外部網頁內容，必須解決以下三個核心問題：

## 問題所在

- 模型（llama-server）本身無網路能力，只能處理傳入的文字
- 瀏覽器前端存在 **CORS** 限制，無法直接 `fetch` 任意外部網域
- 需要一個「中介層」來替模型取得網頁內容

## 架構選擇比較

### 方案 A：Tool Calling（最推薦）

**流程**：
1. 前端定義 `fetch_url` tool 並傳送給模型（符合 OpenAI function calling 格式）
2. 模型判斷需要外部資訊 → 回傳 `tool_calls`
3. 前端收到 `tool_calls` 後，呼叫本機 proxy 取得網頁內容
4. 將取得的內容以 `tool` role 訊息形式塞回對話歷史
5. 再次送給模型 → 模型根據內容生成最終回答

**優點**：
- 模型自主決定何時需要抓網頁
- 最接近現代 LLM Agent 行為
- Qwen3.5 已原生支援 OpenAI 格式的 function/tool calling

### 方案 B：使用者貼 URL → 前端自動預抓

**流程**：
- 使用者輸入文字中含有 URL
- 前端正則偵測 URL
- 呼叫本機 proxy 抓取內容
- 將抓到的內容注入 system message 或作為額外 user message
- 直接送給模型

**優點**：
- 不需要 tool calling 支援
- 實作相對簡單快速
- 使用者體驗接近直接貼連結

### 方案 C：使用者自己貼上網頁內容

使用者手動 Ctrl+A → Ctrl+C → 貼上內容  
最簡單，但完全不自動化，體驗最差。

## 必要新增元件

1. **本機 Proxy Server**（解決瀏覽器 CORS 問題）

   ```text
   fetch_proxy.py（建議使用 FastAPI，約 30 行）
   • 接受 POST { "url": "https://..." }
   • requests.get(url) 取得內容
   • 回傳純文字（或壓縮後文字）
   • 運行於 http://localhost:8001

前端修改（chat.js 或對應檔案）
方案 A：實作 tool calling 完整迴圈
送出 tools 定義
處理 finish_reason: "tool_calls"
執行 proxy 請求
把結果以 tool role 加回 messages 再送一次

方案 B：簡單版 URL 偵測
送出前用正則匹配 url
呼叫 proxy 取得內容
附加到 system prompt 或新增一條 user message



建議實作順序（由易到難）

先完成 fetch_proxy.py
→ 獨立 FastAPI 小服務，port 8001
修改 start.sh / 啟動腳本
→ 同時啟動 llama-server + proxy server
修改前端 chat.js
先做方案 B（URL 自動預抓）→ 最快看到效果
再視需求升級到方案 A（完整 Tool Calling）