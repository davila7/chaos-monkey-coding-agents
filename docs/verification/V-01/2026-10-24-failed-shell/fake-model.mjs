import { createServer } from 'node:http';
import { appendFileSync } from 'node:fs';
const [port, logPath] = process.argv.slice(2);
const script = [
  ['Bash', { command: "cat /app/db.conf; seq 1 9; exit 3", description: 'failing' }],
  ['Bash', { command: "cat /app/db.conf; seq 1 9", description: 'passing' }],
];
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
    const n = msg.messages.flatMap((m) => (Array.isArray(m.content) ? m.content : [])).filter((c) => c.type === 'tool_result').length;
    const step = msg.tools?.length ? script[n] : undefined;
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
}).listen(Number(port), '127.0.0.1');
