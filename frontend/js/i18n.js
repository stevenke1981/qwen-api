// ── Translations ──────────────────────────────────────────────────────────────
const TRANSLATIONS = {
  en: {
    settings:         'Settings',
    clear:            'Clear',
    stop:             'Stop',
    copy:             'Copy',
    copied:           'Copied!',
    apiServer:        'API Server',
    model:            'Model',
    maxTokens:        'Max tokens',
    temperature:      'Temperature',
    systemPrompt:     'System prompt',
    thinkOn:          'Think: ON',
    thinkOff:         'Think: OFF',
    welcome:          'Start chatting below. Thinking blocks are collapsed by default.',
    cleared:          'Conversation cleared.',
    hint:             'Ctrl+Enter to send',
    inputPlaceholder: 'Type a message… (Ctrl+Enter to send)',
    roleUser:         'You',
    roleAssistant:    'Qwen',
    thinking:         'Thinking',
    statusConnecting: 'Connecting...',
    statusOnline:     'Online',
    statusOffline:    'Offline',
    statusError:      'Server error',
    quote:            'Quote',
    quoteHint:        'Select text to quote partially, or click to quote full message',
    fetching:         'Fetching {n} URL(s)…',
    fetchError:       'Failed to fetch',
  },
  'zh-TW': {
    settings:         '設定',
    clear:            '清除',
    stop:             '停止',
    copy:             '複製',
    copied:           '已複製！',
    apiServer:        'API 伺服器',
    model:            '模型',
    maxTokens:        '最大 Token',
    temperature:      '溫度',
    systemPrompt:     '系統提示詞',
    thinkOn:          '思考：開',
    thinkOff:         '思考：關',
    welcome:          '請在下方開始對話，思考區塊預設為收合狀態。',
    cleared:          '對話已清除。',
    hint:             'Ctrl+Enter 送出',
    inputPlaceholder: '輸入訊息…（Ctrl+Enter 送出）',
    roleUser:         '您',
    roleAssistant:    'Qwen',
    thinking:         '思考中',
    statusConnecting: '連線中…',
    statusOnline:     '連線正常',
    statusOffline:    '離線',
    statusError:      '伺服器錯誤',
    quote:            '引用',
    quoteHint:        '選取文字可部分引用，或點擊引用完整訊息',
    fetching:         '抓取 {n} 個網址中…',
    fetchError:       '無法抓取',
  },
  'zh-CN': {
    settings:         '设置',
    clear:            '清除',
    stop:             '停止',
    copy:             '复制',
    copied:           '已复制！',
    apiServer:        'API 服务器',
    model:            '模型',
    maxTokens:        '最大 Token',
    temperature:      '温度',
    systemPrompt:     '系统提示词',
    thinkOn:          '思考：开',
    thinkOff:         '思考：关',
    welcome:          '请在下方开始对话，思考区块默认为折叠状态。',
    cleared:          '对话已清除。',
    hint:             'Ctrl+Enter 发送',
    inputPlaceholder: '输入消息…（Ctrl+Enter 发送）',
    roleUser:         '您',
    roleAssistant:    'Qwen',
    thinking:         '思考中',
    statusConnecting: '连接中…',
    statusOnline:     '连接正常',
    statusOffline:    '离线',
    statusError:      '服务器错误',
    quote:            '引用',
    quoteHint:        '选取文字可部分引用，或点击引用完整消息',
    fetching:         '抓取 {n} 个网址中…',
    fetchError:       '无法抓取',
  },
  ja: {
    settings:         '設定',
    clear:            'クリア',
    stop:             '停止',
    copy:             'コピー',
    copied:           'コピー済み！',
    apiServer:        'API サーバー',
    model:            'モデル',
    maxTokens:        '最大トークン',
    temperature:      '温度',
    systemPrompt:     'システムプロンプト',
    thinkOn:          '思考：ON',
    thinkOff:         '思考：OFF',
    welcome:          '下のフィールドからチャットを開始してください。思考ブロックはデフォルトで折りたたまれています。',
    cleared:          '会話をクリアしました。',
    hint:             'Ctrl+Enter で送信',
    inputPlaceholder: 'メッセージを入力…（Ctrl+Enter で送信）',
    roleUser:         'あなた',
    roleAssistant:    'Qwen',
    thinking:         '考え中',
    statusConnecting: '接続中…',
    statusOnline:     'オンライン',
    statusOffline:    'オフライン',
    statusError:      'サーバーエラー',
    quote:            '引用',
    quoteHint:        'テキストを選択して部分引用、またはクリックで全文引用',
    fetching:         '{n} 件のURLを取得中…',
    fetchError:       '取得失敗',
  },
};

let _lang = 'en';

/** Return the current language code. */
export function getLang() { return _lang; }

/** Set active language (must be a key in TRANSLATIONS). */
export function setLang(lang) {
  if (TRANSLATIONS[lang]) _lang = lang;
}

/** Translate a key using the current language, fallback to English. */
export function t(key) {
  return (TRANSLATIONS[_lang] || TRANSLATIONS.en)[key] ?? key;
}

/**
 * Detect the best-matching supported language from the browser's
 * navigator.languages list. Returns one of: 'en' | 'zh-TW' | 'zh-CN' | 'ja'
 */
export function detectLang() {
  const candidates = Array.from(navigator.languages?.length ? navigator.languages : [navigator.language || 'en']);
  for (const lang of candidates) {
    const l = lang.toLowerCase();
    if (l.startsWith('zh-tw') || l.startsWith('zh-hant')) return 'zh-TW';
    if (l.startsWith('zh'))                               return 'zh-CN';
    if (l.startsWith('ja'))                               return 'ja';
    if (l.startsWith('en'))                               return 'en';
  }
  return 'en';
}

/** Apply current language to all [data-i18n] elements and the input placeholder. */
export function applyLang() {
  document.documentElement.lang = _lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  const inputEl = document.getElementById('user-input');
  if (inputEl) inputEl.placeholder = t('inputPlaceholder');
}
