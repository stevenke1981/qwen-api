import { fetchPageText } from './webfetch.js';

// ── Tool definitions (OpenAI function calling format) ─────────────────────────
export const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'web_fetch',
      description: 'Fetch and read the text content of a web page. Use this when the user provides a URL or asks you to read, summarize, or analyze a website.',
      parameters: {
        type: 'object',
        properties: {
          url: {
            type: 'string',
            description: 'The full URL to fetch (must start with http:// or https://)',
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
];

// ── Tool executor ─────────────────────────────────────────────────────────────
export async function executeTool(name, argsStr) {
  let args;
  try {
    args = JSON.parse(argsStr || '{}');
  } catch {
    throw new Error(`Invalid tool arguments: ${argsStr}`);
  }

  if (name === 'web_fetch') {
    const result = await fetchPageText(args.url, args.max_chars ?? 6000);
    const parts  = [];
    if (result.title) parts.push(`Title: ${result.title}`);
    parts.push(`URL: ${result.url}`);
    parts.push('');
    parts.push(result.text);
    if (result.truncated) parts.push(`\n[Content truncated — ${result.total_chars} chars total]`);
    return parts.join('\n');
  }

  throw new Error(`Unknown tool: ${name}`);
}
