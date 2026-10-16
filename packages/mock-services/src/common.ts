import type { CallToolResult } from '@modelcontextprotocol/sdk/types.js';

export class NotFound extends Error {}
export class BadRequest extends Error {}
export class Conflict extends Error {}

export interface Mutation {
  seq: number;
  tool: string;
  args: Record<string, unknown>;
  replayed: boolean;
  result: unknown;
}

/** Service clock: starts at the fixture's `now`; every write advances it by one second. */
export class Clock {
  private ms: number;

  constructor(now: string) {
    this.ms = Date.parse(now);
    if (Number.isNaN(this.ms)) throw new Error(`invalid fixture clock ${now}`);
  }

  tick(): string {
    this.ms += 1000;
    return new Date(this.ms).toISOString().replace('.000Z', 'Z');
  }
}

/** Audit log of every write. A repeated idempotency key (scoped per tool) replays the first result. */
export class MutationLog {
  private readonly idem = new Map<string, unknown>();
  readonly entries: Mutation[] = [];

  run<T>(tool: string, args: Record<string, unknown>, key: string | undefined, fn: () => T): T {
    const scoped = key === undefined ? undefined : `${tool}\u0000${key}`;
    if (scoped !== undefined && this.idem.has(scoped)) {
      const result = this.idem.get(scoped) as T;
      this.entries.push({ seq: this.entries.length, tool, args, replayed: true, result });
      return result;
    }
    const result = fn();
    if (scoped !== undefined) this.idem.set(scoped, result);
    this.entries.push({ seq: this.entries.length, tool, args, replayed: false, result });
    return result;
  }
}

export function page<T>(hits: T[], n: number | undefined, size: number) {
  const p = n ?? 1;
  if (!Number.isInteger(p) || p < 1) throw new BadRequest('400 Bad Request: page must be a positive integer');
  const start = (p - 1) * size;
  return { results: hits.slice(start, start + size), page: p, next_page: start + size < hits.length ? p + 1 : null, total: hits.length };
}

function ok(value: unknown): CallToolResult {
  return { content: [{ type: 'text', text: JSON.stringify(value) }] };
}

/** Domain errors become tool errors with an HTTP-style message; anything else is a server bug and propagates. */
export function guarded(fn: () => unknown): CallToolResult {
  try {
    return ok(fn());
  } catch (e) {
    if (e instanceof NotFound || e instanceof BadRequest || e instanceof Conflict) return { content: [{ type: 'text', text: e.message }], isError: true };
    throw e;
  }
}
