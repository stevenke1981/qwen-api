import { getLang } from './i18n.js';

const STORAGE_KEY = 'qwen_chat_settings';

export const DEFAULTS = {
  apiUrl:       'http://192.168.80.60:8000',
  model:        'qwen',
  maxTokens:    '6144',
  temperature:  '0.1',
  systemPrompt: `You are a helpful assistant with web search and web fetch tools.\nRULES:\n- For any question about current events, news, rankings, prices, or facts that may have changed, you MUST call web_search FIRST before answering.\n- When searching for rankings or lists (e.g. "top 3 repos"), write a specific query — e.g. "github most starred repositories 2026".\n- Never answer from memory when the information could be outdated.\n- Calling get_datetime does NOT replace web_search. If you need current data, call web_search — include the year in your query if needed.\n- Do NOT search again after you already have results — use what you got.\n- After searching, summarize the results directly and cite the source URL.`,
};

/**
 * Load saved settings into form fields.
 * Returns the saved language code (or null if none was saved).
 */
export function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    if (saved.apiUrl        != null) document.getElementById('api-url').value       = saved.apiUrl;
    if (saved.model         != null) document.getElementById('model-name').value    = saved.model;
    if (saved.maxTokens     != null) document.getElementById('max-tokens').value    = saved.maxTokens;
    if (saved.temperature   != null) document.getElementById('temperature').value   = saved.temperature;
    if (saved.systemPrompt  != null) document.getElementById('system-prompt').value = saved.systemPrompt;
    return { lang: saved.lang || null, thinking: saved.thinking ?? false };
  } catch {
    return { lang: null, thinking: false };
  }
}

/** Reset all settings to defaults and clear localStorage. */
export function resetSettings() {
  localStorage.removeItem(STORAGE_KEY);
  document.getElementById('api-url').value       = DEFAULTS.apiUrl;
  document.getElementById('model-name').value    = DEFAULTS.model;
  document.getElementById('max-tokens').value    = DEFAULTS.maxTokens;
  document.getElementById('temperature').value   = DEFAULTS.temperature;
  document.getElementById('system-prompt').value = DEFAULTS.systemPrompt;
}

/** Persist current form values and active language to localStorage. */
export function saveSettings(thinking) {
  const prev = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  const settings = {
    apiUrl:       document.getElementById('api-url').value.trim(),
    model:        document.getElementById('model-name').value.trim(),
    maxTokens:    document.getElementById('max-tokens').value,
    temperature:  document.getElementById('temperature').value,
    systemPrompt: document.getElementById('system-prompt').value,
    lang:         getLang(),
    thinking:     thinking !== undefined ? thinking : (prev.thinking ?? false),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
