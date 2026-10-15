import { createServer, request as httpRequest, type IncomingHttpHeaders, type IncomingMessage, type Server } from 'node:http';
import { canonicalArgs, FAULT_PHASE, type CallSignature, type CapabilityClass, type FaultDecision, type FaultEngine } from '@cmca/fault-engine';

export const DEFAULT_PAYLOAD_CAP = 64 * 1024;

export interface ProxyOptions {
  /**
   * Upstream MCP endpoint per server name, served at `/<name>/mcp`: an http URL,
   * or `unix:<socket path>:<request path>` for a service reachable only over a
   * socket the agent container does not mount.
   */
  upstreams: Record<string, string>;
  /** Absent: pure pass-through, nothing is logged. */
  engine?: FaultEngine | undefined;
  sig?: { taskId: string; attempt: number; harness: string } | undefined;
  payloadCap?: number;
  /** Proxy events that are not engine decisions (oversized responses, upstream errors). */
  onEvent?: (e: Record<string, unknown>) => void;
  sleep?: (ms: number) => Promise<void>;
}

interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: string | number;
  method: string;
  params?: { name?: unknown; arguments?: unknown };
}

interface ToolResult {
  content?: { type: string; text?: string }[];
  structuredContent?: unknown;
  isError?: boolean;
  [k: string]: unknown;
}

type Upstream = URL | { socketPath: string; path: string };

export function parseUpstream(spec: string): Upstream {
  if (!spec.startsWith('unix:')) return new URL(spec);
  const rest = spec.slice('unix:'.length);
  const i = rest.lastIndexOf(':');
  if (i <= 0) throw new Error(`invalid unix upstream ${spec}`);
  return { socketPath: rest.slice(0, i), path: rest.slice(i + 1) };
}

const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'host', 'content-length', 'te', 'trailer']);

function forwardHeaders(h: IncomingHttpHeaders): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};
  for (const [k, v] of Object.entries(h)) if (v !== undefined && !HOP_BY_HOP.has(k)) out[k] = v;
  return out;
}

async function readAll(stream: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const c of stream) chunks.push(c as Buffer);
  return Buffer.concat(chunks);
}

function isToolCall(v: unknown): v is JsonRpcRequest {
  if (v === null || typeof v !== 'object' || Array.isArray(v)) return false;
  const m = v as Record<string, unknown>;
  return m.method === 'tools/call' && (typeof m.id === 'string' || typeof m.id === 'number');
}

/** The JSON-RPC message with `id` from a JSON or SSE response body. */
export function extractResponse(body: string, contentType: string, id: string | number): { result?: ToolResult; error?: unknown } | null {
  const pick = (v: unknown) => {
    if (v && typeof v === 'object' && (v as { id?: unknown }).id === id) return v as { result?: ToolResult; error?: unknown };
    return null;
  };
  if (contentType.includes('text/event-stream')) {
    for (const event of body.split(/\r?\n\r?\n/)) {
      const data = event
        .split(/\r?\n/)
        .filter((l) => l.startsWith('data:'))
        .map((l) => l.slice(5).replace(/^ /, ''))
        .join('\n');
      if (!data) continue;
      try {
        const hit = pick(JSON.parse(data));
        if (hit) return hit;
      } catch {
        // not JSON: skip the event
      }
    }
    return null;
  }
  try {
    return pick(JSON.parse(body));
  } catch {
    return null;
  }
}

function textOf(r: ToolResult): string {
  return (r.content ?? []).filter((c) => c.type === 'text').map((c) => c.text ?? '').join('');
}

function errorResult(text: string): ToolResult {
  return { content: [{ type: 'text', text }], isError: true };
}

/** Result after a post-phase decision. Non-text content and structured content are dropped once the text changes. */
export function transformResult(engine: FaultEngine, d: FaultDecision, r: ToolResult): ToolResult {
  if (!d.inject || !d.type || FAULT_PHASE[d.type] !== 'post') return r;
  if (d.type === 'falsefail') return errorResult(engine.payload(d));
  const original = textOf(r);
  const text = engine.applyOutput(d, original);
  if (text === original && d.type !== 'empty') return r;
  const { structuredContent: _drop, content: _c, ...rest } = r;
  return { ...rest, content: [{ type: 'text', text }] };
}

export function createProxy(opts: ProxyOptions): Server {
  const cap = opts.payloadCap ?? DEFAULT_PAYLOAD_CAP;
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const emit = (e: Record<string, unknown>) => {
    try {
      opts.onEvent?.({ ts: new Date().toISOString(), ...e });
    } catch {
      // proxy events are best effort
    }
  };

  const upstream = (target: Upstream, method: string, headers: Record<string, string | string[]>, body?: Buffer) =>
    new Promise<IncomingMessage>((done, fail) => {
      const req = 'socketPath' in target ? httpRequest({ ...target, method, headers }, done) : httpRequest(target, { method, headers }, done);
      req.on('error', fail);
      req.end(body);
    });

  return createServer(async (req, res) => {
    const [, server, leaf, ...rest] = (req.url ?? '/').split('?')[0]!.split('/');
    const target = server !== undefined && leaf === 'mcp' && rest.length === 0 ? opts.upstreams[server] : undefined;
    if (!target) {
      res.writeHead(404, { 'content-type': 'text/plain' }).end('404 Not Found\n');
      return;
    }
    const url = parseUpstream(target);
    const headers = forwardHeaders(req.headers);
    try {
      const raw = req.method === 'POST' ? await readAll(req) : undefined;
      let msg: unknown;
      try {
        msg = raw && raw.length > 0 ? JSON.parse(raw.toString('utf8')) : undefined;
      } catch {
        msg = undefined;
      }

      if (!(opts.engine && opts.sig && isToolCall(msg))) {
        const up = await upstream(url, req.method ?? 'GET', headers, raw);
        res.writeHead(up.statusCode ?? 502, forwardHeaders(up.headers));
        up.pipe(res);
        return;
      }

      const engine = opts.engine;
      const name = typeof msg.params?.name === 'string' ? msg.params.name : '';
      const args = msg.params?.arguments ?? {};
      const capability = `mcp.${server}.${name}` as CapabilityClass;
      const sig: CallSignature = {
        ...opts.sig,
        toolName: name,
        capability,
        canonicalArgs: canonicalArgs(capability, args, { workspaceRoot: '/' }),
        args,
      };
      const d = engine.evaluate(sig);
      const reply = (result: ToolResult) => {
        const body = JSON.stringify({ jsonrpc: '2.0', id: msg.id, result });
        res.writeHead(200, { 'content-type': 'application/json' }).end(body);
      };

      if (d.inject && d.type && FAULT_PHASE[d.type] === 'pre') {
        if (d.type === 'latency') await sleep(d.delayMs ?? 0);
        else {
          reply(errorResult(engine.payload(d)));
          return;
        }
      }

      const up = await upstream(url, 'POST', headers, raw);
      const upBody = await readAll(up);
      const contentType = String(up.headers['content-type'] ?? '');
      const parsed = up.statusCode === 200 ? extractResponse(upBody.toString('utf8'), contentType, msg.id) : null;
      if (!parsed || !parsed.result) {
        // Protocol errors and unparseable bodies are relayed as they are.
        res.writeHead(up.statusCode ?? 502, forwardHeaders(up.headers)).end(upBody);
        return;
      }
      if (upBody.length > cap) {
        emit({ event: 'oversize', tool: capability, bytes: upBody.length, cap });
        reply(errorResult(`413 Payload Too Large: response of ${upBody.length} bytes exceeds the ${cap} byte limit`));
        return;
      }
      if (!(d.inject && d.type && FAULT_PHASE[d.type] === 'post')) {
        res.writeHead(200, forwardHeaders(up.headers)).end(upBody);
        return;
      }
      let out: ToolResult;
      try {
        out = transformResult(engine, d, parsed.result);
      } catch {
        out = parsed.result;
      }
      reply(out);
    } catch (e) {
      emit({ event: 'upstream_error', server, error: e instanceof Error ? e.message : String(e) });
      if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain' });
      res.end('502 Bad Gateway\n');
    }
  });
}
