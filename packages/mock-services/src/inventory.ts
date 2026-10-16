import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { BadRequest, Clock, Conflict, guarded, MutationLog, NotFound, page, type Mutation } from './common.js';
import type { Service } from './server.js';

export const REASONS = ['receipt', 'shipment', 'count', 'damage', 'transfer'] as const;
export const INVENTORY_PAGE_SIZE = 5;

const Item = z
  .object({
    sku: z.string(),
    name: z.string(),
    category: z.string(),
    unit: z.string(),
    reorder_point: z.number().int().nonnegative(),
    discontinued: z.boolean(),
    /** On-hand quantity per warehouse; a warehouse missing here does not stock the item. */
    stock: z.record(z.string(), z.number().int().nonnegative()),
  })
  .strict();

const Adjustment = z
  .object({
    id: z.string(),
    sku: z.string(),
    warehouse: z.string(),
    delta: z.number().int(),
    reason: z.enum(REASONS),
    reference: z.string(),
    at: z.string(),
  })
  .strict();

export const InventoryFixtureSchema = z
  .object({
    schema: z.literal('inventory-fixture/1'),
    now: z.string(),
    warehouses: z.array(z.string()).min(1),
    items: z.array(Item),
    adjustments: z.array(Adjustment),
  })
  .strict();

export type Item = z.infer<typeof Item>;
export type Adjustment = z.infer<typeof Adjustment>;
export type InventoryFixture = z.infer<typeof InventoryFixtureSchema>;

export interface InventorySnapshot {
  schema: 'inventory-state/1';
  items: Item[];
  adjustments: Adjustment[];
  mutations: Mutation[];
}

export interface QueryArgs {
  text?: string | undefined;
  category?: string | undefined;
  warehouse?: string | undefined;
  below_reorder?: boolean | undefined;
  include_discontinued?: boolean | undefined;
  page?: number | undefined;
}

const total = (i: Item) => Object.values(i.stock).reduce((a, b) => a + b, 0);

/** Deterministic in-memory stock ledger. `adjust_stock` has no idempotency key: every call is a new adjustment. */
export class InventoryStore {
  private readonly warehouses: Set<string>;
  private readonly items = new Map<string, Item>();
  private readonly adjustments: Adjustment[];
  private readonly log = new MutationLog();
  private readonly clock: Clock;
  private nextAdjustment: number;

  constructor(fixture: InventoryFixture) {
    const f = InventoryFixtureSchema.parse(fixture);
    this.warehouses = new Set(f.warehouses);
    for (const i of f.items) {
      if (this.items.has(i.sku)) throw new Error(`duplicate sku ${i.sku}`);
      for (const w of Object.keys(i.stock)) if (!this.warehouses.has(w)) throw new Error(`${i.sku}: unknown warehouse ${w}`);
      this.items.set(i.sku, structuredClone(i));
    }
    this.adjustments = structuredClone(f.adjustments);
    this.nextAdjustment = this.adjustments.length + 1;
    this.clock = new Clock(f.now);
  }

  private get(sku: string): Item {
    const i = this.items.get(sku);
    if (!i) throw new NotFound(`404 Not Found: item ${sku} does not exist`);
    return i;
  }

  private warehouse(w: string): void {
    if (!this.warehouses.has(w)) throw new NotFound(`404 Not Found: warehouse ${w} does not exist`);
  }

  query(a: QueryArgs) {
    if (a.warehouse !== undefined) this.warehouse(a.warehouse);
    const q = a.text?.toLowerCase();
    const hits = [...this.items.values()]
      .filter(
        (i) =>
          (a.include_discontinued || !i.discontinued) &&
          (a.category === undefined || i.category === a.category) &&
          (a.warehouse === undefined || a.warehouse in i.stock) &&
          (q === undefined || i.name.toLowerCase().includes(q) || i.sku.toLowerCase().includes(q)),
      )
      .map((i) => ({ i, on_hand: a.warehouse === undefined ? total(i) : i.stock[a.warehouse]! }))
      .filter(({ i, on_hand }) => !a.below_reorder || on_hand < i.reorder_point)
      .sort((x, y) => (x.i.sku < y.i.sku ? -1 : 1));
    const p = page(hits, a.page, INVENTORY_PAGE_SIZE);
    return {
      ...p,
      results: p.results.map(({ i, on_hand }) => ({ sku: i.sku, name: i.name, category: i.category, unit: i.unit, on_hand, reorder_point: i.reorder_point })),
    };
  }

  item(sku: string) {
    const i = structuredClone(this.get(sku));
    return { ...i, on_hand: total(i) };
  }

  listAdjustments(a: { sku?: string | undefined; warehouse?: string | undefined; reference?: string | undefined; page?: number | undefined }) {
    if (a.sku !== undefined) this.get(a.sku);
    if (a.warehouse !== undefined) this.warehouse(a.warehouse);
    // Newest first, so the first page shows what was just written.
    const hits = this.adjustments
      .filter((x) => (a.sku === undefined || x.sku === a.sku) && (a.warehouse === undefined || x.warehouse === a.warehouse) && (a.reference === undefined || x.reference === a.reference))
      .reverse();
    return page(structuredClone(hits), a.page, INVENTORY_PAGE_SIZE);
  }

  adjust(a: { sku: string; warehouse: string; delta: number; reason: (typeof REASONS)[number]; reference?: string | undefined }) {
    const i = this.get(a.sku);
    this.warehouse(a.warehouse);
    if (!Number.isInteger(a.delta) || a.delta === 0) throw new BadRequest('400 Bad Request: delta must be a non-zero integer');
    return this.log.run('adjust_stock', a, undefined, () => {
      const now = i.stock[a.warehouse] ?? 0;
      if (now + a.delta < 0) throw new Conflict(`409 Conflict: ${a.sku} has ${now} on hand in ${a.warehouse}; cannot apply ${a.delta}`);
      i.stock[a.warehouse] = now + a.delta;
      const adj: Adjustment = { id: `adj-${this.nextAdjustment++}`, sku: a.sku, warehouse: a.warehouse, delta: a.delta, reason: a.reason, reference: a.reference ?? '', at: this.clock.tick() };
      this.adjustments.push(adj);
      return { adjustment_id: adj.id, sku: a.sku, warehouse: a.warehouse, on_hand: i.stock[a.warehouse], at: adj.at };
    });
  }

  snapshot(): InventorySnapshot {
    return {
      schema: 'inventory-state/1',
      items: [...this.items.values()].sort((x, y) => (x.sku < y.sku ? -1 : 1)).map((i) => structuredClone(i)),
      adjustments: structuredClone(this.adjustments),
      mutations: structuredClone(this.log.entries),
    };
  }
}

export function inventoryService(store: InventoryStore): Service {
  return {
    name: 'inventory',
    version: '2.3.0',
    snapshot: () => store.snapshot(),
    register(s: McpServer, write) {
      s.registerTool(
        'query',
        {
          description: `List stock items. Filters are optional and combine with AND. on_hand is the quantity in the given warehouse, or across all warehouses when none is given. Discontinued items are left out unless include_discontinued is true. Results are sorted by sku, ${INVENTORY_PAGE_SIZE} per page; follow next_page until it is null.`,
          inputSchema: {
            text: z.string().optional().describe('Case-insensitive substring of the name or sku'),
            category: z.string().optional(),
            warehouse: z.string().optional(),
            below_reorder: z.boolean().optional().describe('Only items whose on_hand is below their reorder_point'),
            include_discontinued: z.boolean().optional(),
            page: z.number().int().min(1).optional().describe('1-based page number'),
          },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.query(a)),
      );
      s.registerTool(
        'get_item',
        {
          description: 'Get one item with its stock per warehouse and its total on_hand.',
          inputSchema: { sku: z.string().min(1) },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.item(a.sku)),
      );
      s.registerTool(
        'list_adjustments',
        {
          description: `List stock adjustments, newest first, ${INVENTORY_PAGE_SIZE} per page. Filters are optional and combine with AND.`,
          inputSchema: {
            sku: z.string().optional(),
            warehouse: z.string().optional(),
            reference: z.string().optional().describe('Exact reference given to adjust_stock'),
            page: z.number().int().min(1).optional().describe('1-based page number'),
          },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.listAdjustments(a)),
      );
      s.registerTool(
        'adjust_stock',
        {
          description:
            'Add delta (negative to remove) to the on-hand quantity of an item in one warehouse and record an adjustment. Every call records a new adjustment, including a repeated call with the same arguments and reference. Fails without a change if the quantity would go below zero.',
          inputSchema: {
            sku: z.string().min(1),
            warehouse: z.string().min(1),
            delta: z.number().int(),
            reason: z.enum(REASONS),
            reference: z.string().optional().describe('Free text stored on the adjustment, such as an order or count id'),
          },
        },
        async (a) => write(() => store.adjust(a)),
      );
    },
  };
}
