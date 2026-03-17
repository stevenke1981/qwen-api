import { t } from './i18n.js';

export function setStatus(state, label) {
  document.getElementById('status-dot').className  = `dot ${state}`;
  document.getElementById('status-text').textContent = label;
}

export async function checkHealth() {
  const base = document.getElementById('api-url').value.trim();
  setStatus('', t('statusConnecting'));
  try {
    const r = await fetch(`${base}/health`, { signal: AbortSignal.timeout(3000) });
    r.ok ? setStatus('online', t('statusOnline'))
         : setStatus('error',  t('statusError'));
  } catch {
    setStatus('error', t('statusOffline'));
  }
}
