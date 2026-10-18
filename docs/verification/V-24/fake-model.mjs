// Fake Anthropic Messages API for offline harness checks (no model call).
// The first request that declares a tool whose name ends with TOOL_SUFFIX gets
// a tool_use of that tool with TOOL_INPUT; any request that already carries a
// tool_result, or declares no such tool, gets a final text. Every request body
// is appended to LOG, so the log shows what the model would see.
import { createServer } from 'node:http';
import { appendFileSync } from 'node:fs';

const port = Number(process.env.PORT ?? 9000);
const log = process.env.LOG ?? '/log/requests.jsonl';
const suffix = process.env.TOOL_SUFFIX ?? 'get_ticket';
const input = JSON.parse(process.env.TOOL_INPUT ?? '{"id": 501}');

createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    let msg = null;
    try {
      msg = body ? JSON.parse(body) : null;
    } catch {}
    appendFileSync(log, JSON.stringify({ url: req.url, body: msg }) + '\n');
    if (!req.url.includes('/messages') || !msg) {
      res.writeHead(404, { 'content-type': 'application/json' });
      return res.end('{}');
    }
    const answered = (msg.messages ?? []).some((m) => Array.isArray(m.content) && m.content.some((c) => c.type === 'tool_result'));
    const tool = answered ? null : (msg.tools ?? []).find((t) => typeof t.name === 'string' && t.name.endsWith(suffix));
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const ev = (type, data) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    const usage = { input_tokens: 1, output_tokens: 1 };
    ev('message_start', { message: { id: 'msg_fake', type: 'message', role: 'assistant', model: msg.model, content: [], stop_reason: null, usage } });
    if (tool) {
      ev('content_block_start', { index: 0, content_block: { type: 'tool_use', id: 'toolu_fake', name: tool.name, input: {} } });
      ev('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(input) } });
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
}).listen(port);
