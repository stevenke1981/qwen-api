// ── URL detection & proxy fetch ───────────────────────────────────────────────

const URL_RE = /https?:\/\/[^\s<>"{}|\\^`[\]]+/g;

/** Extract unique URLs from a string. */
export function detectUrls(text) {
  return [...new Set(text.match(URL_RE) || [])];
}

/** Derive proxy base URL from the configured API URL (same host, port 8001). */
function getProxyBase() {
  try {
    const u = new URL(document.getElementById('api-url').value.trim());
    return `${u.protocol}//${u.hostname}:8001`;
  } catch {
    return 'http://localhost:8001';
  }
}

/**
 * Fetch a URL via the local proxy and return:
 *   { url, title, text, truncated, total_chars }
 */
export async function fetchPageText(url, maxChars = 6000) {
  const base = getProxyBase();
  const res  = await fetch(`${base}/fetch`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ url, max_chars: maxChars }),
    signal:  AbortSignal.timeout(20000),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  return res.json();
}

/**
 * Format fetched pages into a context block for the model.
 * This is appended to the user message before sending.
 */
export function buildFetchContext(results) {
  return results.map(r => {
    const label = r.title ? `${r.title} — ${r.url}` : r.url;
    const note  = r.truncated ? ` [truncated, ${r.total_chars} chars total]` : '';
    return `=== Web: ${label}${note} ===\n${r.text}\n=== End ===`;
  }).join('\n\n');
}
