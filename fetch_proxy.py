#!/usr/bin/env python3
"""
Fetch Proxy — 解決瀏覽器 CORS 限制。
端點：
  POST /fetch   抓取網頁回傳純文字
  POST /search  DuckDuckGo 搜尋
預設 port 8001，與 llama-server (8000) 並排執行。
"""

import re
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup

app = FastAPI(title="Fetch Proxy", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; QwenFetchBot/1.0)"}
MAX_DOWNLOAD = 2 * 1024 * 1024   # 2 MB hard cap


# ── /fetch ────────────────────────────────────────────────────────────────────

class FetchReq(BaseModel):
    url:       str
    max_chars: int = 6000


@app.post("/fetch")
async def fetch(req: FetchReq):
    url = req.url.strip()
    # Auto-prepend https:// if missing scheme
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    async with httpx.AsyncClient(
        timeout=15,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        try:
            async with client.stream("GET", url, headers=HEADERS) as r:
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                raw = b""
                async for chunk in r.aiter_bytes(8192):
                    raw += chunk
                    if len(raw) >= MAX_DOWNLOAD:
                        break
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"HTTP {e.response.status_code}: {url}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"Request error: {e}")

    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].strip().split(";")[0]
    try:
        body = raw.decode(charset, errors="replace")
    except LookupError:
        body = raw.decode("utf-8", errors="replace")

    if "html" in content_type:
        soup = BeautifulSoup(body, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript"]):
            tag.decompose()
        title = (soup.title.string or "").strip() if soup.title else ""
        text  = soup.get_text(separator="\n", strip=True)
        text  = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        title = ""
        text  = body.strip()

    truncated = len(text) > req.max_chars
    return {
        "url":         url,
        "title":       title,
        "text":        text[:req.max_chars],
        "truncated":   truncated,
        "total_chars": len(text),
    }


# ── /search ───────────────────────────────────────────────────────────────────

class SearchReq(BaseModel):
    query:       str
    max_results: int = 5
    fetch_top:   int = 0    # auto-fetch full text of top N results (0 = off by default)
    max_chars:   int = 1500 # max chars per fetched page


async def _fetch_text(client: httpx.AsyncClient, url: str, max_chars: int = 1500) -> str:
    """Fetch a URL and return stripped plain text (best-effort)."""
    try:
        async with client.stream("GET", url, headers=HEADERS, timeout=10) as r:
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            raw = b""
            async for chunk in r.aiter_bytes(8192):
                raw += chunk
                if len(raw) >= 512 * 1024:
                    break
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].strip().split(";")[0]
        body = raw.decode(charset, errors="replace")
        if "html" in content_type:
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
        else:
            text = body.strip()
        return text[:max_chars]
    except Exception:
        return ""


@app.post("/search")
async def search(req: SearchReq):
    import asyncio
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise HTTPException(503, "duckduckgo-search not installed. Run: pip install duckduckgo-search")

    print(f"[search] query={req.query!r} max_results={req.max_results} fetch_top={req.fetch_top}", flush=True)

    def _ddg_search():
        print("[search] calling DDGS().text() ...", flush=True)
        with DDGS() as ddgs:
            results = list(ddgs.text(req.query, max_results=req.max_results))
        print(f"[search] DDGS returned {len(results)} results", flush=True)
        return results

    try:
        # Run blocking DDGS call in a thread to avoid blocking the async event loop
        results = await asyncio.wait_for(
            asyncio.to_thread(_ddg_search),
            timeout=20,
        )
    except asyncio.TimeoutError:
        print("[search] DDGS timed out after 20s", flush=True)
        raise HTTPException(504, "Search timed out (DuckDuckGo did not respond in 20s)")
    except Exception as e:
        print(f"[search] DDGS error: {e}", flush=True)
        raise HTTPException(502, f"Search failed: {e}")

    # Auto-fetch full text for top N results
    if req.fetch_top > 0 and results:
        print(f"[search] fetching full text for top {req.fetch_top} URLs ...", flush=True)
        async with httpx.AsyncClient(follow_redirects=True, max_redirects=5) as client:
            texts = await asyncio.gather(*[
                _fetch_text(client, r["href"], req.max_chars)
                for r in results[:req.fetch_top]
            ])
        for i, text in enumerate(texts):
            if text:
                results[i]["full_text"] = text
        print("[search] full text fetch done", flush=True)

    print(f"[search] done, returning {len(results)} results", flush=True)
    return {"query": req.query, "results": results}


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    print(f"=== Fetch Proxy: http://0.0.0.0:{port} (/fetch  /search) ===")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
