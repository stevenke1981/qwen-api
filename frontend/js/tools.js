import { fetchPageText, searchWeb, normalizeUrl } from './webfetch.js';

// ── Tool definitions (OpenAI function calling format) ─────────────────────────
export const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'web_fetch',
      description:
        'Fetch and read the text content of a web page. ' +
        'The URL can be with or without http:// prefix (e.g. "example.com", "www.google.com", "https://example.com"). ' +
        'Use when the user provides a URL or asks to read / summarize a website.',
      parameters: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'URL to fetch. http:// or https:// prefix is optional.',
          },
          max_chars: {
            type: 'integer',
            description: 'Maximum characters to return (default: 6000)',
            default: 6000,
          },
        },
        required: ['url'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'web_search',
      description:
        'Search the web using DuckDuckGo. Use this to find information, discover URLs, or get up-to-date data.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Search query string',
          },
          max_results: {
            type: 'integer',
            description: 'Number of results to return (default: 5, max: 10)',
            default: 5,
          },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'read_file',
      description:
        'Open a file picker so the user can select a local file. ' +
        'Reads and returns the file name and text content. ' +
        'Suitable for .txt, .md, .csv, .json, .py, .js, .html, .xml, .yaml, .log, etc.',
      parameters: {
        type: 'object',
        properties: {
          hint: {
            type: 'string',
            description: 'Optional hint shown to the user about what file is expected',
          },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'write_file',
      description:
        'Save text content to a file and trigger a download in the user\'s browser. ' +
        'Use this to export generated content, code, reports, CSV data, etc.',
      parameters: {
        type: 'object',
        properties: {
          filename: {
            type: 'string',
            description: 'File name including extension (e.g. "report.txt", "data.csv", "script.py")',
          },
          content: {
            type: 'string',
            description: 'Text content to write into the file',
          },
        },
        required: ['filename', 'content'],
      },
    },
  },
];

// ── Tool executor ─────────────────────────────────────────────────────────────

export async function executeTool(name, argsStr) {
  let args;
  try {
    args = JSON.parse(argsStr || '{}');
  } catch {
    throw new Error(`Invalid tool arguments: ${argsStr}`);
  }

  // ── web_fetch ──────────────────────────────────────────────────────────────
  if (name === 'web_fetch') {
    const result = await fetchPageText(normalizeUrl(args.url), args.max_chars ?? 6000);
    const parts  = [];
    if (result.title) parts.push(`Title: ${result.title}`);
    parts.push(`URL: ${result.url}`);
    parts.push('');
    parts.push(result.text);
    if (result.truncated) parts.push(`\n[Content truncated — ${result.total_chars} chars total]`);
    return parts.join('\n');
  }

  // ── web_search ─────────────────────────────────────────────────────────────
  if (name === 'web_search') {
    const { query, results } = await searchWeb(args.query, args.max_results ?? 5);
    if (!results.length) return `No results found for: "${query}"`;
    const lines = [`Search results for: "${query}"\n`];
    results.forEach((r, i) => {
      lines.push(`${i + 1}. ${r.title}`);
      lines.push(`   URL: ${r.href}`);
      if (r.body) lines.push(`   ${r.body}`);
      lines.push('');
    });
    return lines.join('\n');
  }

  // ── read_file ──────────────────────────────────────────────────────────────
  if (name === 'read_file') {
    return readFileFromUser(args.hint);
  }

  // ── write_file ─────────────────────────────────────────────────────────────
  if (name === 'write_file') {
    return writeFileToUser(args.filename, args.content);
  }

  throw new Error(`Unknown tool: ${name}`);
}

// ── File helpers (browser) ────────────────────────────────────────────────────

function readFileFromUser(hint) {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type   = 'file';
    input.accept =
      '.txt,.md,.csv,.json,.js,.ts,.py,.html,.css,.xml,.yaml,.yml,.log,.ini,.toml,.sh,.bat';
    input.style.display = 'none';
    document.body.appendChild(input);

    // File selected
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      document.body.removeChild(input);
      if (!file) { resolve('No file was selected.'); return; }
      try {
        const text    = await file.text();
        const preview = text.length > 8000 ? text.slice(0, 8000) + '\n[Truncated]' : text;
        resolve(`File: ${file.name} (${file.size} bytes)\n\n${preview}`);
      } catch (e) {
        resolve(`Error reading file: ${e.message}`);
      }
    });

    // User cancelled (Chrome 113+ / Firefox 91+)
    input.addEventListener('cancel', () => {
      document.body.removeChild(input);
      resolve('File selection was cancelled by the user.');
    });

    input.click();
  });
}

function writeFileToUser(filename, content) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  return `File "${filename}" has been downloaded (${content.length} chars).`;
}
