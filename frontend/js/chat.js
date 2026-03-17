import { setLang, detectLang, applyLang, t }           from './i18n.js';
import { loadSettings, saveSettings }                   from './settings.js';
import { checkHealth }                                   from './health.js';
import { appendMessage, renderContent, scrollBottom }   from './render.js';
import { TOOLS, executeTool }                            from './tools.js';

// ── DOM refs ──────────────────────────────────────────────────────────────────
const messagesEl     = document.getElementById('messages');
const inputEl        = document.getElementById('user-input');
const sendBtn        = document.getElementById('send-btn');
const stopBtn        = document.getElementById('stop-btn');
const clearBtn       = document.getElementById('clear-btn');
const settingsToggle = document.getElementById('settings-toggle');
const settingsBar    = document.getElementById('settings-bar');
const langSelect     = document.getElementById('lang-select');
const thinkBtn       = document.getElementById('think-btn');

let history         = [];
let abortController = null;
let thinkingEnabled = false;

// ── Startup ───────────────────────────────────────────────────────────────────
const { lang: savedLang, thinking: savedThinking } = loadSettings();
thinkingEnabled  = savedThinking ?? false;
const initLang   = savedLang || detectLang();
setLang(initLang);
langSelect.value = initLang;
applyLang();
updateThinkBtn();
checkHealth();
setInterval(checkHealth, 10000);

// ── Language switcher ─────────────────────────────────────────────────────────
langSelect.addEventListener('change', () => {
  setLang(langSelect.value);
  applyLang();
  updateThinkBtn();
  checkHealth();
  saveSettings();
});

// ── Think toggle ──────────────────────────────────────────────────────────────
function updateThinkBtn() {
  thinkBtn.dataset.i18n = thinkingEnabled ? 'thinkOn' : 'thinkOff';
  thinkBtn.textContent  = t(thinkBtn.dataset.i18n);
  thinkBtn.classList.toggle('active', thinkingEnabled);
}
thinkBtn.addEventListener('click', () => {
  thinkingEnabled = !thinkingEnabled;
  updateThinkBtn();
  saveSettings(thinkingEnabled);
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

// ── Tool status helpers ───────────────────────────────────────────────────────
function showToolStatus(msg) {
  const el = document.getElementById('fetch-status');
  if (el) { el.textContent = msg; el.classList.add('visible'); }
}
function hideToolStatus() {
  document.getElementById('fetch-status')?.classList.remove('visible');
}

/** Show a tool-call indicator block inside the bubble. */
function showToolInBubble(bubble, url) {
  bubble.innerHTML = '';
  const div = document.createElement('div');
  div.className   = 'tool-call-indicator';
  div.textContent = `🔗 ${t('toolFetching').replace('{url}', url)}`;
  bubble.appendChild(div);
}

// ── Streaming call with tool-call accumulation ────────────────────────────────
/**
 * One round of streaming chat completion with tool support.
 * Returns { fullText, toolCalls[], finishReason }
 */
async function streamCall(apiBase, model, messages, maxTokens, temperature, bubble) {
  const res = await fetch(`${apiBase}/v1/chat/completions`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    signal:  abortController.signal,
    body: JSON.stringify({
      model, messages, stream: true,
      max_tokens: maxTokens, temperature,
      tools: TOOLS, tool_choice: 'auto',
    }),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

  const reader      = res.body.getReader();
  const decoder     = new TextDecoder();
  let   fullText    = '';
  let   toolCalls   = [];   // sparse array indexed by tc.index
  let   finishReason = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    for (const line of decoder.decode(value, { stream: true }).split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed === 'data: [DONE]' || !trimmed.startsWith('data: ')) continue;

      try {
        const data   = JSON.parse(trimmed.slice(6));
        const choice = data.choices?.[0];
        if (!choice) continue;

        if (choice.finish_reason) finishReason = choice.finish_reason;
        const delta = choice.delta || {};

        // Accumulate tool_calls chunks
        if (delta.tool_calls) {
          for (const tc of delta.tool_calls) {
            const idx = tc.index ?? 0;
            if (!toolCalls[idx]) {
              toolCalls[idx] = { id: '', type: 'function', function: { name: '', arguments: '' } };
            }
            if (tc.id)                  toolCalls[idx].id                  = tc.id;
            if (tc.function?.name)      toolCalls[idx].function.name      += tc.function.name;
            if (tc.function?.arguments) toolCalls[idx].function.arguments += tc.function.arguments;
          }
        }

        // Stream text content
        if (delta.content) {
          fullText += delta.content;
          renderContent(bubble, fullText, true, thinkingEnabled);
          scrollBottom();
        }
      } catch { /* skip malformed chunks */ }
    }
  }

  return { fullText, toolCalls: toolCalls.filter(Boolean), finishReason };
}

// ── Main send ─────────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || abortController) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';

  // Build user message with think token
  const token   = thinkingEnabled ? '/think' : '/no_think';
  const payload = `${token}\n${text}`;
  history.push({ role: 'user', content: payload });
  appendMessage('user').textContent = text;

  const bubble = appendMessage('assistant');
  bubble.classList.add('cursor');

  sendBtn.style.display = 'none';
  stopBtn.style.display = 'inline-block';
  inputEl.disabled      = true;
  abortController       = new AbortController();

  const apiBase      = document.getElementById('api-url').value.trim();
  const model        = document.getElementById('model-name').value.trim();
  const maxTokens    = parseInt(document.getElementById('max-tokens').value);
  const temperature  = parseFloat(document.getElementById('temperature').value);
  const systemPrompt = document.getElementById('system-prompt').value.trim();

  // Messages sent to API (includes system prompt, excludes it from persistent history)
  const messages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...history]
    : [...history];

  let finalText = '';

  try {
    // ── Tool calling loop ───────────────────────────────────────────────────
    while (true) {
      const { fullText, toolCalls, finishReason } =
        await streamCall(apiBase, model, messages, maxTokens, temperature, bubble);

      if (finishReason === 'tool_calls' && toolCalls.length > 0) {
        // 1. Record assistant's tool_call turn in messages
        messages.push({
          role:       'assistant',
          content:    fullText || null,
          tool_calls: toolCalls,
        });

        // 2. Execute each tool and append result
        for (const call of toolCalls) {
          let args = {};
          try { args = JSON.parse(call.function.arguments || '{}'); } catch { /* */ }

          const url = args.url || call.function.name;
          showToolInBubble(bubble, url);
          showToolStatus(t('toolFetching').replace('{url}', url));

          let result;
          try {
            result = await executeTool(call.function.name, call.function.arguments);
          } catch (e) {
            result = `Error executing tool "${call.function.name}": ${e.message}`;
          }

          messages.push({ role: 'tool', tool_call_id: call.id, content: result });
        }

        hideToolStatus();
        bubble.innerHTML = ''; // clear indicator, next iteration streams the real answer
        continue;
      }

      // No more tool calls — this is the final answer
      finalText = fullText;
      break;
    }
  } catch (e) {
    if (e.name !== 'AbortError') bubble.textContent = `Request failed: ${e.message}`;
  } finally {
    renderContent(bubble, finalText, false, thinkingEnabled);
    bubble.classList.remove('cursor');
    hideToolStatus();

    if (finalText) history.push({ role: 'assistant', content: finalText });

    abortController       = null;
    sendBtn.style.display = 'inline-block';
    stopBtn.style.display = 'none';
    inputEl.disabled      = false;
    inputEl.focus();
    scrollBottom();
  }
}
