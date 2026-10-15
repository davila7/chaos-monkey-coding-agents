import { z } from 'zod';

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

export interface Mutation {
  seq: number;
  tool: string;
  args: Record<string, unknown>;
  replayed: boolean;
  result: unknown;
}

export interface Snapshot {
  schema: 'tickets-state/1';
  tickets: Ticket[];
  mutations: Mutation[];
}

export class NotFound extends Error {}
export class BadRequest extends Error {}

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
  private readonly idem = new Map<string, unknown>();
  private readonly mutations: Mutation[] = [];
  private clock: number;
  private nextId: number;
  private nextComment = 1;

  constructor(fixture: Fixture) {
    const f = FixtureSchema.parse(fixture);
    for (const t of f.tickets) {
      if (this.tickets.has(t.id)) throw new Error(`duplicate ticket id ${t.id}`);
      this.tickets.set(t.id, structuredClone(t));
      this.nextComment += t.comments.length;
    }
    this.clock = Date.parse(f.now);
    if (Number.isNaN(this.clock)) throw new Error(`invalid fixture clock ${f.now}`);
    this.nextId = Math.max(0, ...this.tickets.keys()) + 1;
  }

  private tick(): string {
    this.clock += 1000;
    return new Date(this.clock).toISOString().replace('.000Z', 'Z');
  }

  private get(id: number): Ticket {
    const t = this.tickets.get(id);
    if (!t) throw new NotFound(`404 Not Found: ticket ${id} does not exist`);
    return t;
  }

  private mutate<T>(tool: string, args: Record<string, unknown>, key: string | undefined, fn: () => T): T {
    const scoped = key === undefined ? undefined : `${tool}\u0000${key}`;
    if (scoped !== undefined && this.idem.has(scoped)) {
      const result = this.idem.get(scoped) as T;
      this.mutations.push({ seq: this.mutations.length, tool, args, replayed: true, result });
      return result;
    }
    const result = fn();
    if (scoped !== undefined) this.idem.set(scoped, result);
    this.mutations.push({ seq: this.mutations.length, tool, args, replayed: false, result });
    return result;
  }

  search(a: SearchArgs) {
    const page = a.page ?? 1;
    if (!Number.isInteger(page) || page < 1) throw new BadRequest('400 Bad Request: page must be a positive integer');
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
    const start = (page - 1) * PAGE_SIZE;
    const results = hits.slice(start, start + PAGE_SIZE).map(({ id, title, status, priority, team, labels, updated_at }) => ({
      id,
      title,
      status,
      priority,
      team,
      labels,
      updated_at,
    }));
    return { results, page, next_page: start + PAGE_SIZE < hits.length ? page + 1 : null, total: hits.length };
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
      const ts = this.tick();
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
      const ts = this.tick();
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
        t.updated_at = this.tick();
      }
      return { id: t.id, status: t.status, previous_status: previous };
    });
  }

  snapshot(): Snapshot {
    return {
      schema: 'tickets-state/1',
      tickets: [...this.tickets.values()].sort((x, y) => x.id - y.id).map((t) => structuredClone(t)),
      mutations: structuredClone(this.mutations),
    };
  }
}
