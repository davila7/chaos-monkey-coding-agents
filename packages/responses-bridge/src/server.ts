import Anthropic from '@anthropic-ai/sdk';
import { appendFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import { convertOutput, convertRequest, convertUsage, ToolNames, type Options, type ResponsesRequest } from './convert.js';

export interface BridgeConfig extends Options {
  client: Pick<Anthropic, 'messages'>;
  /** JSONL file that gets one line per model response: id, model, usage. */
  usageLog?: string;
  /** Interval of `response.in_progress` events while a response is being generated. */
  keepAliveMs?: number;
}

function sse(res: ServerResponse, event: Record<string, unknown> & { type: string }): void {
  res.write(`event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
}

async function body(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  return Buffer.concat(chunks).toString('utf8');
}

function fail(res: ServerResponse, status: number, message: string, type = 'invalid_request_error'): void {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify({ error: { type, message } }));
}

/**
 * Serves `POST <any>/responses` by calling the Messages API and answering as
 * a Responses API event stream. The HTTP status is sent once the model
 * stream has started, so a refused request (429, 529, 400) reaches Codex as
 * that status and Codex's own retry policy applies; a failure after that
 * point is sent as `response.failed`.
 */
export async function handle(cfg: BridgeConfig, req: IncomingMessage, res: ServerResponse): Promise<void> {
  const path = (req.url ?? '').split('?')[0]!;
  if (req.method === 'GET' && path.endsWith('/models')) {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ models: [] }));
    return;
  }
  if (req.method !== 'POST' || !path.endsWith('/responses')) return fail(res, 404, `no route for ${req.method} ${path}`);

  let parsed: ResponsesRequest;
  try {
    parsed = JSON.parse(await body(req)) as ResponsesRequest;
  } catch {
    return fail(res, 400, 'request body is not JSON');
  }
  const names = new ToolNames();
  const params = convertRequest(parsed, names, cfg);
  const stream = cfg.client.messages.stream(params);

  let started = false;
  let timer: NodeJS.Timeout | undefined;
  const start = (id: string) => {
    if (started) return;
    started = true;
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
    sse(res, { type: 'response.created', response: { id, status: 'in_progress' } });
    timer = setInterval(() => sse(res, { type: 'response.in_progress', response: { id, status: 'in_progress' } }), cfg.keepAliveMs ?? 10_000);
  };
  stream.on('streamEvent', (e) => {
    if (e.type === 'message_start') start(e.message.id);
  });

  try {
    const msg = await stream.finalMessage();
    start(msg.id);
    clearInterval(timer);
    if (cfg.usageLog) {
      appendFileSync(cfg.usageLog, `${JSON.stringify({ id: msg.id, model: msg.model, stop_reason: msg.stop_reason, usage: msg.usage })}\n`);
    }
    const items = convertOutput(msg, names);
    items.forEach((item, i) => {
      sse(res, { type: 'response.output_item.added', output_index: i, item });
      sse(res, { type: 'response.output_item.done', output_index: i, item });
    });
    const usage = convertUsage(msg.usage);
    const incomplete = msg.stop_reason === 'max_tokens';
    sse(res, {
      type: incomplete ? 'response.incomplete' : 'response.completed',
      response: {
        id: msg.id,
        status: incomplete ? 'incomplete' : 'completed',
        ...(incomplete ? { incomplete_details: { reason: 'max_output_tokens' } } : {}),
        output: items,
        usage,
      },
    });
    res.end();
  } catch (err) {
    clearInterval(timer);
    const status = err instanceof Anthropic.APIError && typeof err.status === 'number' ? err.status : 502;
    const message = err instanceof Error ? err.message : String(err);
    if (!started) return fail(res, status, message, status === 429 ? 'rate_limit_error' : 'api_error');
    sse(res, { type: 'response.failed', response: { status: 'failed', error: { code: 'server_error', message } } });
    res.end();
  }
}

export function serve(cfg: BridgeConfig, port: number, host = '127.0.0.1'): Promise<Server> {
  const server = createServer((req, res) => {
    handle(cfg, req, res).catch((err: unknown) => {
      if (!res.headersSent) fail(res, 500, err instanceof Error ? err.message : String(err), 'api_error');
      else res.end();
    });
  });
  return new Promise((done) => server.listen(port, host, () => done(server)));
}
