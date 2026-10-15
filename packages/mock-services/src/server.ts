import { renameSync, writeFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server } from 'node:http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
import { guarded } from './common.js';

/** A mock service: its MCP tools and the state the verifier reads. */
export interface Service {
  name: string;
  version: string;
  register(server: McpServer, write: (fn: () => unknown) => CallToolResult): void;
  snapshot(): unknown;
}

/** One MCP server per request: the SDK's stateless pattern. Tool state lives in the service's store. */
export function mcpServer(service: Service, onWrite: () => void): McpServer {
  const s = new McpServer({ name: service.name, version: service.version });
  service.register(s, (fn) => {
    const r = guarded(fn);
    onWrite();
    return r;
  });
  return s;
}

export function writeSnapshot(service: Service, path: string): void {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(service.snapshot(), null, 2)}\n`);
  renameSync(tmp, path);
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  const raw = Buffer.concat(chunks).toString('utf8');
  return raw === '' ? undefined : JSON.parse(raw);
}

export function httpServer(service: Service, statePath: string | null): Server {
  const onWrite = () => {
    if (statePath) writeSnapshot(service, statePath);
  };
  return createServer(async (req, res) => {
    const path = (req.url ?? '/').split('?')[0];
    if (path === '/healthz') {
      res.writeHead(200, { 'content-type': 'text/plain' }).end('ok\n');
      return;
    }
    if (path !== '/mcp') {
      res.writeHead(404, { 'content-type': 'text/plain' }).end('404 Not Found\n');
      return;
    }
    if (req.method !== 'POST') {
      res.writeHead(405, { allow: 'POST', 'content-type': 'text/plain' }).end('405 Method Not Allowed\n');
      return;
    }
    let body: unknown;
    try {
      body = await readBody(req);
    } catch {
      res.writeHead(400, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32700, message: 'Parse error' }, id: null }));
      return;
    }
    const server = mcpServer(service, onWrite);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.on('close', () => {
      void transport.close();
      void server.close();
    });
    await server.connect(transport);
    await transport.handleRequest(req, res, body);
  });
}
