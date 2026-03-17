import { getLang } from './i18n.js';

const STORAGE_KEY = 'qwen_chat_settings';

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
    return saved.lang || null;
  } catch {
    return null;
  }
}

/** Persist current form values and active language to localStorage. */
export function saveSettings() {
  const settings = {
    apiUrl:       document.getElementById('api-url').value.trim(),
    model:        document.getElementById('model-name').value.trim(),
    maxTokens:    document.getElementById('max-tokens').value,
    temperature:  document.getElementById('temperature').value,
    systemPrompt: document.getElementById('system-prompt').value,
    lang:         getLang(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
