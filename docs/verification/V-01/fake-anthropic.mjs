// Fake Anthropic Messages endpoint for conformance dry runs. Picks a script
// from the probe path in the conversation and answers with one tool call per
// turn, then a final text. Requests without tools get plain text.
import { createServer } from 'node:http';
import { appendFileSync } from 'node:fs';
const [port, harness, logPath] = process.argv.slice(2);
const N = {
  'claude-code': { read: 'Read', write: 'Write', edit: 'Edit', search: 'Grep', list: 'LS', bash: 'Bash', fp: 'file_path', old: 'old_string', nw: 'new_string' },
  opencode: { read: 'read', write: 'write', edit: 'edit', search: 'grep', list: 'list', bash: 'bash', fp: 'filePath', old: 'oldString', nw: 'newString' },
  pi: { read: 'read', write: 'write', edit: 'edit', search: 'grep', list: 'ls', bash: 'bash', fp: 'path', old: 'oldText', nw: 'newText' },
}[harness];
const scripts = [
  ['probe/answer.txt', [[N.write, { [N.fp]: '/app/probe/answer.txt', content: 'ready' }]]],
  ['probe/config.txt', [[N.read, { [N.fp]: '/app/probe/config.txt' }], [N.edit, { [N.fp]: '/app/probe/config.txt', [N.old]: 'mode=off', [N.nw]: 'mode=on' }]]],
  ['probe/docs', [[N.search, { pattern: 'marigold', path: '/app/probe/docs' }]]],
  ['probe/items', [[N.list, { path: '/app/probe/items' }]]],
  ['shell.done', [[N.bash, { command: 'cat /app/probe/notes.txt; touch /app/probe/shell.done', description: 'run' }]]],
  ['probe/notes.txt', [[N.read, { [N.fp]: '/app/probe/notes.txt' }]]],
];
const textOf = (m) => (typeof m.content === 'string' ? m.content : m.content.map((c) => c.text ?? '').join(' '));
createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    appendFileSync(logPath, JSON.stringify({ url: req.url, body: body ? JSON.parse(body) : null }) + '\n');
    if (!req.url.includes('/messages') || req.url.includes('count_tokens')) {
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ input_tokens: 1 }));
    }
    const msg = JSON.parse(body);
    const first = textOf(msg.messages.find((m) => m.role === 'user') ?? { content: '' });
    const script = msg.tools?.length ? (scripts.find(([k]) => first.includes(k))?.[1] ?? []) : [];
    const n = msg.messages.flatMap((m) => (Array.isArray(m.content) ? m.content : [])).filter((c) => c.type === 'tool_result').length;
    const step = script[n];
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const ev = (type, data) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    ev('message_start', { message: { id: `msg_${n}`, type: 'message', role: 'assistant', model: msg.model, content: [], stop_reason: null, usage: { input_tokens: 1, output_tokens: 1 } } });
    if (step) {
      ev('content_block_start', { index: 0, content_block: { type: 'tool_use', id: `toolu_${Date.now()}_${n}`, name: step[0], input: {} } });
      ev('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(step[1]) } });
      ev('content_block_stop', { index: 0 });
      ev('message_delta', { delta: { stop_reason: 'tool_use' }, usage: { output_tokens: 1 } });
    } else {
      ev('content_block_start', { index: 0, content_block: { type: 'text', text: '' } });
      ev('content_block_delta', { index: 0, delta: { type: 'text_delta', text: 'done' } });
      ev('content_block_stop', { index: 0 });
      ev('message_delta', { delta: { stop_reason: 'end_turn' }, usage: { output_tokens: 1 } });
    }
    ev('message_stop', {});
    res.end();
  });
}).listen(Number(port), '0.0.0.0');
