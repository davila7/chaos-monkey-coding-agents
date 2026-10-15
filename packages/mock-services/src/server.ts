import { renameSync, writeFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server } from 'node:http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { BadRequest, NotFound, PAGE_SIZE, PRIORITIES, STATUSES, TicketStore } from './tickets.js';

function ok(value: unknown): CallToolResult {
  return { content: [{ type: 'text', text: JSON.stringify(value) }] };
}

function guarded(fn: () => unknown): CallToolResult {
  try {
    return ok(fn());
  } catch (e) {
    if (e instanceof NotFound || e instanceof BadRequest) return { content: [{ type: 'text', text: e.message }], isError: true };
    throw e;
  }
}

/** One MCP server per request: the SDK's stateless pattern. Tool state lives in `store`. */
export function mcpServer(store: TicketStore, onWrite: () => void): McpServer {
  const s = new McpServer({ name: 'tickets', version: '1.4.2' });
  const write = (fn: () => unknown) => {
    const r = guarded(fn);
    onWrite();
    return r;
  };
  s.registerTool(
    'search_tickets',
    {
      description: `Search tickets. All filters are optional and combine with AND. Results are sorted by id, ${PAGE_SIZE} per page; follow next_page until it is null.`,
      inputSchema: {
        query: z.string().optional().describe('Case-insensitive substring of the title'),
        status: z.enum(STATUSES).optional(),
        label: z.string().optional(),
        team: z.string().optional(),
        priority: z.enum(PRIORITIES).optional(),
        page: z.number().int().min(1).optional().describe('1-based page number'),
      },
      annotations: { readOnlyHint: true },
    },
    async (a) => guarded(() => store.search(a)),
  );
  s.registerTool(
    'get_ticket',
    {
      description: 'Get one ticket with its body, customer and comments.',
      inputSchema: { id: z.number().int().positive() },
      annotations: { readOnlyHint: true },
    },
    async (a) => guarded(() => store.ticket(a.id)),
  );
  s.registerTool(
    'create_ticket',
    {
      description:
        'Create a ticket. Each call creates a new ticket unless idempotency_key repeats a previous create_ticket call, in which case the original result is returned.',
      inputSchema: {
        title: z.string().min(1),
        body: z.string(),
        team: z.string().optional(),
        priority: z.enum(PRIORITIES).optional(),
        customer: z.string().optional(),
        labels: z.array(z.string()).optional(),
        idempotency_key: z.string().min(1).optional(),
      },
    },
    async (a) => write(() => store.create(a)),
  );
  s.registerTool(
    'add_comment',
    {
      description:
        'Add a comment to a ticket. Each call adds a new comment unless idempotency_key repeats a previous add_comment call, in which case the original result is returned.',
      inputSchema: {
        id: z.number().int().positive(),
        body: z.string().min(1),
        author: z.string().optional(),
        idempotency_key: z.string().min(1).optional(),
      },
    },
    async (a) => write(() => store.comment(a)),
  );
  s.registerTool(
    'update_status',
    {
      description: 'Set the status of a ticket. Setting the current status again changes nothing.',
      inputSchema: { id: z.number().int().positive(), status: z.enum(STATUSES) },
      annotations: { idempotentHint: true },
    },
    async (a) => write(() => store.setStatus(a)),
  );
  return s;
}

export function writeSnapshot(store: TicketStore, path: string): void {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(store.snapshot(), null, 2)}\n`);
  renameSync(tmp, path);
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  const raw = Buffer.concat(chunks).toString('utf8');
  return raw === '' ? undefined : JSON.parse(raw);
}

export function httpServer(store: TicketStore, statePath: string | null): Server {
  const onWrite = () => {
    if (statePath) writeSnapshot(store, statePath);
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
    const server = mcpServer(store, onWrite);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.on('close', () => {
      void transport.close();
      void server.close();
    });
    await server.connect(transport);
    await transport.handleRequest(req, res, body);
  });
}
