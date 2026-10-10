// Fake Anthropic Messages API: answers with the scripted tool calls in order,
// then a final text. Logs every request body (what the model would see).
import { createServer } from 'node:http';
import { appendFileSync, readFileSync } from 'node:fs';
const [port, scriptPath, logPath] = process.argv.slice(2);
const script = JSON.parse(readFileSync(scriptPath, 'utf8'));
createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    appendFileSync(logPath, JSON.stringify({ url: req.url, body: body ? JSON.parse(body) : null }) + '\n');
    if (!req.url.includes('/messages')) { res.writeHead(404); return res.end('{}'); }
    const msg = JSON.parse(body);
    const toolResults = msg.messages.flatMap((m) => (Array.isArray(m.content) ? m.content : [])).filter((c) => c.type === 'tool_result').length;
    const step = script[toolResults];
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    const ev = (type, data) => res.write(`event: ${type}\ndata: ${JSON.stringify({ type, ...data })}\n\n`);
    ev('message_start', { message: { id: `msg_${toolResults}`, type: 'message', role: 'assistant', model: msg.model, content: [], stop_reason: null, usage: { input_tokens: 1, output_tokens: 1 } } });
    if (step) {
      ev('content_block_start', { index: 0, content_block: { type: 'tool_use', id: `toolu_${toolResults}`, name: step.name, input: {} } });
      ev('content_block_delta', { index: 0, delta: { type: 'input_json_delta', partial_json: JSON.stringify(step.input) } });
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
}).listen(Number(port));
