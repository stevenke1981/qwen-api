// ── Proxy helpers ─────────────────────────────────────────────────────────────

/** Derive proxy base URL from the configured API URL (same host, port 8001). */
function getProxyBase() {
  try {
    const u = new URL(document.getElementById('api-url').value.trim());
    return `${u.protocol}//${u.hostname}:8001`;
  } catch {
    return 'http://localhost:8001';
  }
}

/** Normalize URL — prepend https:// if no scheme present. */
export function normalizeUrl(url) {
  url = url.trim();
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

// ── /fetch ────────────────────────────────────────────────────────────────────

/**
 * Fetch a URL via the local proxy.
 * Returns { url, title, text, truncated, total_chars }
 */
export async function fetchPageText(url, maxChars = 6000) {
  const base = getProxyBase();
  console.debug('[fetchPageText] proxy=', base, 'url=', url);
  const res  = await fetch(`${base}/fetch`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ url: normalizeUrl(url), max_chars: maxChars }),
    signal:  AbortSignal.timeout(20000),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  return res.json();
}

// ── /search ───────────────────────────────────────────────────────────────────

/**
 * Web search via DuckDuckGo (through proxy).
 * Returns { query, results: [{ title, href, body }] }
 */
export async function searchWeb(query, maxResults = 5) {
  const base = getProxyBase();
  console.debug('[searchWeb] proxy=', base, 'query=', query);
  const res  = await fetch(`${base}/search`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ query, max_results: maxResults }),
    signal:  AbortSignal.timeout(30000),
  });
  console.debug('[searchWeb] response status=', res.status);
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  const data = await res.json();
  console.debug('[searchWeb] results=', data.results?.length);
  return data;
}
