import { t } from './i18n.js';

export function scrollBottom() {
  const el = document.getElementById('messages');
  el.scrollTop = el.scrollHeight;
}

export function appendMessage(role) {
  const messagesEl = document.getElementById('messages');

  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;

  const roleLabel = document.createElement('div');
  roleLabel.className = 'msg-role';
  roleLabel.textContent = role === 'user' ? t('roleUser') : t('roleAssistant');
  wrap.appendChild(roleLabel);

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  wrap.appendChild(bubble);

  messagesEl.appendChild(wrap);
  scrollBottom();
  return bubble;
}

function createCodeBlock(lang, code) {
  const block = document.createElement('div');
  block.className = 'code-block';

  const header = document.createElement('div');
  header.className = 'code-block-header';

  const langLabel = document.createElement('span');
  langLabel.className = 'lang-label';
  langLabel.textContent = lang || 'text';

  const copyBtn = document.createElement('button');
  copyBtn.className = 'copy-btn';
  copyBtn.textContent = t('copy');
  copyBtn.addEventListener('click', () => {
    const success = () => {
      copyBtn.textContent = t('copied');
      copyBtn.classList.add('copied');
      setTimeout(() => { copyBtn.textContent = t('copy'); copyBtn.classList.remove('copied'); }, 2000);
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(code).then(success).catch(fallback);
    } else {
      fallback();
    }
    function fallback() {
      const ta = Object.assign(document.createElement('textarea'), {
        value: code,
        style: 'position:fixed;opacity:0',
      });
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      success();
    }
  });

  header.appendChild(langLabel);
  header.appendChild(copyBtn);

  const pre    = document.createElement('pre');
  const codeEl = document.createElement('code');
  codeEl.textContent = code;
  pre.appendChild(codeEl);

  block.appendChild(header);
  block.appendChild(pre);
  return block;
}

/**
 * Render assistant text into `bubble`, handling:
 *   - fenced code blocks  (```lang\ncode\n```)
 *   - <think>…</think> blocks
 *   - streaming cursor on the last text segment
 */
export function renderContent(bubble, text, streaming) {
  bubble.innerHTML = '';

  // Split by fenced code blocks
  const codeRe = /```(\w*)\n([\s\S]*?)```/g;
  const segments = [];
  let lastIndex = 0;
  let match;

  while ((match = codeRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: 'code', lang: match[1], content: match[2] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }

  segments.forEach((seg, si) => {
    if (seg.type === 'code') {
      bubble.appendChild(createCodeBlock(seg.lang, seg.content));
      return;
    }

    // Within text segments, handle <think> blocks
    const parts     = seg.content.split(/(<think>[\s\S]*?<\/think>|<think>[\s\S]*$)/);
    const isLastSeg = si === segments.length - 1;

    parts.forEach((part, pi) => {
      if (part.startsWith('<think>')) {
        const inner = part.replace(/^<think>/, '').replace(/<\/think>$/, '');

        const block  = document.createElement('div');
        block.className = 'thinking-block collapsed';

        const hdr = document.createElement('div');
        hdr.className = 'thinking-header';
        hdr.innerHTML = `<span class="arrow">▼</span> ${t('thinking')}`;
        hdr.addEventListener('click', () => block.classList.toggle('collapsed'));

        const body = document.createElement('div');
        body.className  = 'thinking-body';
        body.textContent = inner;

        block.appendChild(hdr);
        block.appendChild(body);
        bubble.appendChild(block);
      } else if (part) {
        const span = document.createElement('span');
        span.textContent = part;
        if (streaming && isLastSeg && pi === parts.length - 1) span.className = 'cursor';
        bubble.appendChild(span);
      }
    });
  });
}
