import type { AddressInfo } from 'node:net';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { httpServer, TicketStore, ticketsService, type Fixture, type Ticket } from '../src/index.js';

function ticket(id: number, over: Partial<Ticket> = {}): Ticket {
  return {
    id,
    title: `Ticket ${id}`,
    body: '',
    status: 'open',
    priority: 'P3',
    team: 'billing',
    customer: `cust-${id}`,
    labels: [],
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    comments: [],
    ...over,
  };
}

const fixture: Fixture = {
  schema: 'tickets-fixture/1',
  now: '2026-09-10T12:00:00Z',
  tickets: Array.from({ length: 12 }, (_, i) => ticket(i + 1, { labels: i % 2 ? ['vip'] : [] })),
};

describe('TicketStore', () => {
  it('paginates by id with next_page', () => {
    const s = new TicketStore(fixture);
    const p1 = s.search({});
    expect(p1.results.map((t) => t.id)).toEqual([1, 2, 3, 4, 5]);
    expect(p1).toMatchObject({ page: 1, next_page: 2, total: 12 });
    expect(s.search({ page: 3 })).toMatchObject({ next_page: null });
    expect(s.search({ label: 'vip' }).total).toBe(6);
  });

  it('replays an idempotency key without a second write', () => {
    const s = new TicketStore(fixture);
    const a = s.comment({ id: 3, body: 'x', idempotency_key: 'k1' });
    const b = s.comment({ id: 3, body: 'x', idempotency_key: 'k1' });
    s.comment({ id: 3, body: 'x' });
    expect(b).toEqual(a);
    const snap = s.snapshot();
    expect(snap.tickets[2]?.comments).toHaveLength(2);
    expect(snap.mutations.map((m) => m.replayed)).toEqual([false, true, false]);
  });

  it('scopes idempotency keys per tool', () => {
    const s = new TicketStore(fixture);
    s.create({ title: 't', body: '', idempotency_key: 'same' });
    s.comment({ id: 1, body: 'c', idempotency_key: 'same' });
    expect(s.snapshot().mutations.every((m) => !m.replayed)).toBe(true);
  });

  it('is deterministic for the same call sequence', () => {
    const run = () => {
      const s = new TicketStore(fixture);
      s.create({ title: 'n', body: 'b' });
      s.setStatus({ id: 2, status: 'closed' });
      s.comment({ id: 2, body: 'done' });
      return JSON.stringify(s.snapshot());
    };
    expect(run()).toBe(run());
  });

  it('reports a missing ticket as not found', () => {
    expect(() => new TicketStore(fixture).ticket(99)).toThrow(/404 Not Found/);
  });
});

describe('MCP over streamable HTTP', () => {
  const dir = mkdtempSync(join(tmpdir(), 'tickets-'));
  const statePath = join(dir, 'state.json');
  const server = httpServer(ticketsService(new TicketStore(fixture)), statePath);
  let url: URL;

  beforeAll(async () => {
    await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
    url = new URL(`http://127.0.0.1:${(server.address() as AddressInfo).port}/mcp`);
  });
  afterAll(() => new Promise<void>((done) => server.close(() => done())));

  it('lists the five tools and serves calls', async () => {
    const client = new Client({ name: 't', version: '0' });
    await client.connect(new StreamableHTTPClientTransport(url));
    const tools = (await client.listTools()).tools.map((t) => t.name).sort();
    expect(tools).toEqual(['add_comment', 'create_ticket', 'get_ticket', 'search_tickets', 'update_status']);

    const r = await client.callTool({ name: 'update_status', arguments: { id: 4, status: 'resolved' } });
    expect(JSON.parse((r.content as { text: string }[])[0]!.text)).toEqual({ id: 4, status: 'resolved', previous_status: 'open' });
    const state = JSON.parse(readFileSync(statePath, 'utf8'));
    expect(state.tickets[3].status).toBe('resolved');

    const miss = await client.callTool({ name: 'get_ticket', arguments: { id: 404 } });
    expect(miss.isError).toBe(true);
    await client.close();
  });
});
