import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { Clock, guarded, MutationLog, NotFound, page, type Mutation } from './common.js';
import type { Service } from './server.js';

export const STATUSES = ['open', 'pending', 'resolved', 'closed', 'duplicate'] as const;
export const PRIORITIES = ['P1', 'P2', 'P3', 'P4'] as const;
export const PAGE_SIZE = 5;

const Comment = z.object({ id: z.string(), author: z.string(), body: z.string(), created_at: z.string() }).strict();

const Ticket = z
  .object({
    id: z.number().int().positive(),
    title: z.string(),
    body: z.string(),
    status: z.enum(STATUSES),
    priority: z.enum(PRIORITIES),
    team: z.string(),
    customer: z.string(),
    labels: z.array(z.string()),
    created_at: z.string(),
    updated_at: z.string(),
    comments: z.array(Comment),
  })
  .strict();

export const FixtureSchema = z
  .object({
    schema: z.literal('tickets-fixture/1'),
    /** Service clock at start; every write advances it by one second. */
    now: z.string(),
    tickets: z.array(Ticket),
  })
  .strict();

export type Ticket = z.infer<typeof Ticket>;
export type Fixture = z.infer<typeof FixtureSchema>;

export interface Snapshot {
  schema: 'tickets-state/1';
  tickets: Ticket[];
  mutations: Mutation[];
}

export interface SearchArgs {
  query?: string | undefined;
  status?: string | undefined;
  label?: string | undefined;
  team?: string | undefined;
  priority?: string | undefined;
  page?: number | undefined;
}

/** Deterministic in-memory ticket store. All writes go through `mutate` so the audit log is complete. */
export class TicketStore {
  private readonly tickets = new Map<number, Ticket>();
  private readonly log = new MutationLog();
  private readonly clock: Clock;
  private nextId: number;
  private nextComment = 1;

  constructor(fixture: Fixture) {
    const f = FixtureSchema.parse(fixture);
    for (const t of f.tickets) {
      if (this.tickets.has(t.id)) throw new Error(`duplicate ticket id ${t.id}`);
      this.tickets.set(t.id, structuredClone(t));
      this.nextComment += t.comments.length;
    }
    this.clock = new Clock(f.now);
    this.nextId = Math.max(0, ...this.tickets.keys()) + 1;
  }

  private get(id: number): Ticket {
    const t = this.tickets.get(id);
    if (!t) throw new NotFound(`404 Not Found: ticket ${id} does not exist`);
    return t;
  }

  private mutate<T>(tool: string, args: Record<string, unknown>, key: string | undefined, fn: () => T): T {
    return this.log.run(tool, args, key, fn);
  }

  search(a: SearchArgs) {
    const q = a.query?.toLowerCase();
    const hits = [...this.tickets.values()]
      .filter(
        (t) =>
          (a.status === undefined || t.status === a.status) &&
          (a.label === undefined || t.labels.includes(a.label)) &&
          (a.team === undefined || t.team === a.team) &&
          (a.priority === undefined || t.priority === a.priority) &&
          (q === undefined || t.title.toLowerCase().includes(q)),
      )
      .sort((x, y) => x.id - y.id);
    const p = page(hits, a.page, PAGE_SIZE);
    const results = p.results.map(({ id, title, status, priority, team, labels, updated_at }) => ({ id, title, status, priority, team, labels, updated_at }));
    return { results, page: p.page, next_page: p.next_page, total: p.total };
  }

  ticket(id: number): Ticket {
    return structuredClone(this.get(id));
  }

  create(a: {
    title: string;
    body: string;
    team?: string | undefined;
    priority?: (typeof PRIORITIES)[number] | undefined;
    customer?: string | undefined;
    labels?: string[] | undefined;
    idempotency_key?: string | undefined;
  }) {
    return this.mutate('create_ticket', a, a.idempotency_key, () => {
      const ts = this.clock.tick();
      const t: Ticket = {
        id: this.nextId++,
        title: a.title,
        body: a.body,
        status: 'open',
        priority: a.priority ?? 'P3',
        team: a.team ?? 'unassigned',
        customer: a.customer ?? '',
        labels: [...(a.labels ?? [])],
        created_at: ts,
        updated_at: ts,
        comments: [],
      };
      this.tickets.set(t.id, t);
      return { id: t.id, status: t.status, created_at: t.created_at };
    });
  }

  comment(a: { id: number; body: string; author?: string | undefined; idempotency_key?: string | undefined }) {
    const t = this.get(a.id);
    return this.mutate('add_comment', a, a.idempotency_key, () => {
      const ts = this.clock.tick();
      const c = { id: `c-${this.nextComment++}`, author: a.author ?? 'agent', body: a.body, created_at: ts };
      t.comments.push(c);
      t.updated_at = ts;
      return { ticket_id: t.id, comment_id: c.id, created_at: ts };
    });
  }

  setStatus(a: { id: number; status: (typeof STATUSES)[number] }) {
    const t = this.get(a.id);
    return this.mutate('update_status', a, undefined, () => {
      const previous = t.status;
      if (previous !== a.status) {
        t.status = a.status;
        t.updated_at = this.clock.tick();
      }
      return { id: t.id, status: t.status, previous_status: previous };
    });
  }

  snapshot(): Snapshot {
    return {
      schema: 'tickets-state/1',
      tickets: [...this.tickets.values()].sort((x, y) => x.id - y.id).map((t) => structuredClone(t)),
      mutations: structuredClone(this.log.entries),
    };
  }
}

export function ticketsService(store: TicketStore): Service {
  return {
    name: 'tickets',
    version: '1.4.2',
    snapshot: () => store.snapshot(),
    register(s: McpServer, write) {
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
    },
  };
}
