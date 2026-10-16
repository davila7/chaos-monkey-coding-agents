import type { AddressInfo } from 'node:net';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { describe, expect, it } from 'vitest';
import { DeployStore, deployService, DocsStore, docsService, httpServer, InventoryStore, inventoryService, type Service } from '../src/index.js';

async function withClient(service: Service, statePath: string, fn: (c: Client) => Promise<void>) {
  const server = httpServer(service, statePath);
  await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
  const client = new Client({ name: 't', version: '0' });
  await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${(server.address() as AddressInfo).port}/mcp`)));
  try {
    await fn(client);
  } finally {
    await client.close();
    await new Promise<void>((done) => server.close(() => done()));
  }
}

const text = (r: unknown) => (r as { content: { text: string }[] }).content[0]!.text;

describe('MCP tool sets (SPEC 9.2)', () => {
  const dir = mkdtempSync(join(tmpdir(), 'services-'));

  it('inventory', async () => {
    const store = new InventoryStore({ schema: 'inventory-fixture/1', now: '2026-09-10T12:00:00Z', warehouses: ['east'], items: [{ sku: 'A', name: 'a', category: 'c', unit: 'ea', reorder_point: 1, discontinued: false, stock: { east: 1 } }], adjustments: [] });
    const state = join(dir, 'inventory.json');
    await withClient(inventoryService(store), state, async (c) => {
      expect((await c.listTools()).tools.map((t) => t.name).sort()).toEqual(['adjust_stock', 'get_item', 'list_adjustments', 'query']);
      await c.callTool({ name: 'adjust_stock', arguments: { sku: 'A', warehouse: 'east', delta: 2, reason: 'receipt' } });
      const r = await c.callTool({ name: 'adjust_stock', arguments: { sku: 'A', warehouse: 'east', delta: -9, reason: 'shipment' } });
      expect([r.isError, text(r)]).toEqual([true, '409 Conflict: A has 3 on hand in east; cannot apply -9']);
    });
    expect(JSON.parse(readFileSync(state, 'utf8')).items[0].stock.east).toBe(3);
  });

  it('deploy', async () => {
    const store = new DeployStore({ schema: 'deploy-fixture/1', now: '2026-09-10T12:00:00Z', services: [{ name: 'api', environments: ['prod'] }], builds: [], releases: [], failing_commits: [], degraded_commits: [] });
    const state = join(dir, 'deploy.json');
    await withClient(deployService(store), state, async (c) => {
      expect((await c.listTools()).tools.map((t) => t.name).sort()).toEqual(['build', 'deploy', 'list_services', 'rollback', 'status']);
      const b = JSON.parse(text(await c.callTool({ name: 'build', arguments: { service: 'api', commit: 'abcdef0' } })));
      await c.callTool({ name: 'deploy', arguments: { service: 'api', environment: 'prod', build_id: b.build_id } });
    });
    expect(JSON.parse(readFileSync(state, 'utf8')).releases).toHaveLength(1);
  });

  it('docs', async () => {
    const store = new DocsStore({ schema: 'docs-fixture/1', docs: [{ id: 'a', title: 'A', tags: [], updated_at: '2026-09-01', body: 'alpha' }] });
    await withClient(docsService(store), join(dir, 'docs.json'), async (c) => {
      expect((await c.listTools()).tools.map((t) => t.name).sort()).toEqual(['get_doc', 'search_docs']);
      expect(JSON.parse(text(await c.callTool({ name: 'get_doc', arguments: { id: 'a' } }))).body).toBe('alpha');
    });
  });
});
