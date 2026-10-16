import { describe, expect, it } from 'vitest';
import { InventoryStore, type InventoryFixture, type Item } from '../src/index.js';

const item = (n: number, over: Partial<Item> = {}): Item => ({
  sku: `SKU-${String(n).padStart(3, '0')}`,
  name: `Part ${n}`,
  category: n % 2 ? 'bolts' : 'nuts',
  unit: 'ea',
  reorder_point: 10,
  discontinued: false,
  stock: { east: n, west: 2 * n },
  ...over,
});

const fixture: InventoryFixture = {
  schema: 'inventory-fixture/1',
  now: '2026-09-10T12:00:00Z',
  warehouses: ['east', 'west', 'north'],
  items: [...Array.from({ length: 7 }, (_, i) => item(i + 1)), item(8, { discontinued: true }), item(9, { stock: { north: 0 } })],
  adjustments: [{ id: 'adj-1', sku: 'SKU-001', warehouse: 'east', delta: 1, reason: 'receipt', reference: 'po-1', at: '2026-09-01T00:00:00Z' }],
};

describe('InventoryStore', () => {
  it('filters, totals and paginates by sku', () => {
    const s = new InventoryStore(fixture);
    const p1 = s.query({});
    expect(p1.results.map((r) => r.sku)).toEqual(['SKU-001', 'SKU-002', 'SKU-003', 'SKU-004', 'SKU-005']);
    expect(p1).toMatchObject({ next_page: 2, total: 8 });
    expect(p1.results[1]!.on_hand).toBe(6);
    expect(s.query({ include_discontinued: true }).total).toBe(9);
    expect(s.query({ warehouse: 'north' }).results).toEqual([expect.objectContaining({ sku: 'SKU-009', on_hand: 0 })]);
    // Totals 3, 6, 9 and the north-only item at 0 are below 10.
    expect(s.query({ below_reorder: true }).results.map((r) => r.sku)).toEqual(['SKU-001', 'SKU-002', 'SKU-003', 'SKU-009']);
    expect(s.query({ warehouse: 'east', below_reorder: true }).total).toBe(7);
  });

  it('records every adjustment, including identical repeats', () => {
    const s = new InventoryStore(fixture);
    const a = { sku: 'SKU-002', warehouse: 'east', delta: -1, reason: 'shipment' as const, reference: 'so-9' };
    expect(s.adjust(a)).toEqual({ adjustment_id: 'adj-2', sku: 'SKU-002', warehouse: 'east', on_hand: 1, at: '2026-09-10T12:00:01Z' });
    expect(s.adjust(a).on_hand).toBe(0);
    expect(s.listAdjustments({ reference: 'so-9' }).results.map((x) => x.id)).toEqual(['adj-3', 'adj-2']);
    expect(s.snapshot().mutations).toHaveLength(2);
  });

  it('refuses a negative quantity without a write', () => {
    const s = new InventoryStore(fixture);
    expect(() => s.adjust({ sku: 'SKU-001', warehouse: 'east', delta: -2, reason: 'shipment' })).toThrow(/409 Conflict/);
    expect(() => s.adjust({ sku: 'SKU-001', warehouse: 'east', delta: 0, reason: 'count' })).toThrow(/400 Bad Request/);
    expect(() => s.adjust({ sku: 'SKU-001', warehouse: 'south', delta: 1, reason: 'count' })).toThrow(/404 Not Found/);
    expect(s.snapshot().mutations).toEqual([]);
    expect(s.item('SKU-001').stock.east).toBe(1);
  });

  it('stocks a warehouse the item had no entry for', () => {
    const s = new InventoryStore(fixture);
    s.adjust({ sku: 'SKU-001', warehouse: 'north', delta: 4, reason: 'transfer' });
    expect(s.item('SKU-001')).toMatchObject({ stock: { east: 1, west: 2, north: 4 }, on_hand: 7 });
  });

  it('rejects a fixture with an unknown warehouse', () => {
    expect(() => new InventoryStore({ ...fixture, items: [item(1, { stock: { south: 1 } })] })).toThrow(/unknown warehouse/);
  });
});
