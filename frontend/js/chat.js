import { getLang, setLang, detectLang, applyLang, t } from './i18n.js';
import { loadSettings, saveSettings }                  from './settings.js';
import { checkHealth }                                  from './health.js';
import { appendMessage, renderContent, scrollBottom }  from './render.js';

// ── DOM refs ──────────────────────────────────────────────────────────────────
const messagesEl     = document.getElementById('messages');
const inputEl        = document.getElementById('user-input');
const sendBtn        = document.getElementById('send-btn');
const stopBtn        = document.getElementById('stop-btn');
const clearBtn       = document.getElementById('clear-btn');
const settingsToggle = document.getElementById('settings-toggle');
const settingsBar    = document.getElementById('settings-bar');
const langSelect     = document.getElementById('lang-select');

let history         = [];
let abortController = null;

// ── Startup: load settings → detect / restore language → apply ────────────────
const savedLang = loadSettings();
const initLang  = savedLang || detectLang();
setLang(initLang);
langSelect.value = initLang;
applyLang();
checkHealth();
setInterval(checkHealth, 10000);

// ── Language switcher ─────────────────────────────────────────────────────────
langSelect.addEventListener('change', () => {
  setLang(langSelect.value);
  applyLang();
  checkHealth();   // re-render status text in new language
  saveSettings();
});

// ── Settings panel ────────────────────────────────────────────────────────────
settingsToggle.addEventListener('click', () => settingsBar.classList.toggle('open'));

settingsBar.querySelectorAll('input, textarea').forEach(el => {
  el.addEventListener('change', () => {
    saveSettings();
    if (el.id === 'api-url') checkHealth();
  });
});

// ── Auto-resize textarea ──────────────────────────────────────────────────────
inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
});

// ── Keyboard / button handlers ────────────────────────────────────────────────
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); sendMessage(); }
});
sendBtn.addEventListener('click', sendMessage);
stopBtn.addEventListener('click', () => abortController?.abort());
clearBtn.addEventListener('click', () => {
  history = [];
  messagesEl.innerHTML = `<div class="msg system"><div class="msg-bubble">${t('cleared')}</div></div>`;
});

// ── Main send ─────────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || abortController) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';

  history.push({ role: 'user', content: text });
  appendMessage('user').textContent = text;

  const bubble = appendMessage('assistant');
  bubble.classList.add('cursor');

  sendBtn.style.display = 'none';
  stopBtn.style.display = 'inline-block';
  inputEl.disabled      = true;

  abortController = new AbortController();

  const base         = document.getElementById('api-url').value.trim();
  const model        = document.getElementById('model-name').value.trim();
  const maxTokens    = parseInt(document.getElementById('max-tokens').value);
  const temperature  = parseFloat(document.getElementById('temperature').value);
  const systemPrompt = document.getElementById('system-prompt').value.trim();

  const messages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...history]
    : [...history];

  let fullText = '';

  try {
    const res = await fetch(`${base}/v1/chat/completions`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      signal:  abortController.signal,
      body:    JSON.stringify({ model, messages, stream: true, max_tokens: maxTokens, temperature }),
    });

    if (!res.ok) {
      bubble.textContent = `Error ${res.status}: ${await res.text()}`;
      return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value, { stream: true }).split('\n')) {
        const trimmed = line.trim();
        if (!trimmed || trimmed === 'data: [DONE]' || !trimmed.startsWith('data: ')) continue;
        try {
          const delta = JSON.parse(trimmed.slice(6)).choices?.[0]?.delta?.content;
          if (delta) { fullText += delta; renderContent(bubble, fullText, true); scrollBottom(); }
        } catch { /* skip malformed chunks */ }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') bubble.textContent = `Request failed: ${e.message}`;
  } finally {
    renderContent(bubble, fullText, false);
    bubble.classList.remove('cursor');
    if (fullText) history.push({ role: 'assistant', content: fullText });

    abortController       = null;
    sendBtn.style.display = 'inline-block';
    stopBtn.style.display = 'none';
    inputEl.disabled      = false;
    inputEl.focus();
    scrollBottom();
  }
}
