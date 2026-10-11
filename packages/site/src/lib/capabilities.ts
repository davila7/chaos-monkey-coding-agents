import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';

const count = z.number().int().nonnegative();

const ClassResult = z.object({
  runs: count,
  runs_passed: count,
  exposed: z.boolean(),
  attribution_visible: z.boolean(),
  gap: z.string().optional(),
});

const FaultResult = z.object({
  supported: z.boolean(),
  delivered_as: z.string(),
  attribution_visible: z.boolean(),
  runs_passed: count,
  classes: z.record(z.string(), ClassResult),
});

/** `tt-capabilities/1`, written by `cmca_harbor.conformance report` (D-0020). */
export const Capabilities = z.object({
  schema: z.literal('tt-capabilities/1'),
  harness: z.string().min(1),
  version: z.string().min(1),
  generated_at: z.string(),
  tool_map: z.record(z.string(), z.string()),
  faults: z.record(z.string(), FaultResult),
  parity_set: z.array(z.string()),
  parity_gaps: z.array(z.object({ type: z.string(), capability: z.string(), reason: z.string() })),
  crash_behavior: z.enum(['fail_open', 'fail_closed']),
  injector_p95_ms: z.number().nonnegative(),
});
export type Capabilities = z.infer<typeof Capabilities>;

const DIR = () => join(process.cwd(), 'data/capabilities');

export function loadCapabilities(): Capabilities[] {
  return readdirSync(DIR())
    .filter((f) => f.endsWith('.json'))
    .sort()
    .map((f) => {
      const c = Capabilities.parse(JSON.parse(readFileSync(join(DIR(), f), 'utf8')));
      if (f !== `${c.harness}@${c.version}.json`) throw new Error(`${f}: file name does not match ${c.harness}@${c.version}`);
      return c;
    });
}

/**
 * delivered: every run passed. gap: a reviewed parity gap (D-0017). failed: exposed, not every run passed,
 * and no gap recorded. not_tested: no tool on the harness maps to the class, so conformance skipped it.
 * n/a: the fault type does not apply to the class in the catalog.
 */
export type CellState = 'delivered' | 'gap' | 'failed' | 'not_tested' | 'n/a';

export interface Cell {
  state: CellState;
  runs: number;
  runs_passed: number;
  reason?: string;
}

export const CLASS_ORDER = ['fs.read', 'fs.write', 'fs.edit', 'fs.search', 'fs.list', 'shell'];

const byOrder = (order: string[]) => (a: string, b: string) => {
  const i = order.indexOf(a);
  const j = order.indexOf(b);
  return (i < 0 ? order.length : i) - (j < 0 ? order.length : j) || a.localeCompare(b);
};

export function grid(caps: Capabilities[], c: Capabilities) {
  const classes = [...new Set(caps.flatMap((x) => Object.values(x.faults).flatMap((f) => Object.keys(f.classes))))].sort(
    byOrder(CLASS_ORDER),
  );
  const types = Object.keys(c.faults).sort(byOrder(c.parity_set));
  const applies = new Set(caps.flatMap((x) => Object.entries(x.faults).flatMap(([t, f]) => Object.keys(f.classes).map((k) => `${t}:${k}`))));
  const cells = types.map((t) =>
    classes.map((k): Cell => {
      const r = c.faults[t]!.classes[k];
      if (!r) return { state: applies.has(`${t}:${k}`) ? 'not_tested' : 'n/a', runs: 0, runs_passed: 0 };
      const base = { runs: r.runs, runs_passed: r.runs_passed };
      if (r.gap) return { state: 'gap', ...base, reason: r.gap };
      if (!r.exposed) return { state: 'not_tested', ...base };
      return { state: r.runs > 0 && r.runs_passed === r.runs ? 'delivered' : 'failed', ...base };
    }),
  );
  return { classes, types, cells };
}
