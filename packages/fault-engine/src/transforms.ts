import type { Drift } from './schemas.js';

/** First 30% of the output by code points, with no marker. */
export function truncateHead30(output: string): string {
  const cps = Array.from(output);
  return cps.slice(0, Math.floor(cps.length * 0.3)).join('');
}

function mapJson(value: unknown, fn: (v: unknown) => unknown): unknown {
  const v = fn(value);
  if (Array.isArray(v)) return v.map((x) => mapJson(x, fn));
  if (v !== null && typeof v === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, x] of Object.entries(v)) out[k] = mapJson(x, fn);
    return out;
  }
  return v;
}

/**
 * Applies an author-declared drift variant to a JSON output. Returns null
 * when the output is not JSON, so the caller can pass the original through.
 */
export function applyDrift(output: string, drift: Drift): string | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(output);
  } catch {
    return null;
  }
  let changed: unknown;
  switch (drift.kind) {
    case 'rename_key':
      changed = mapJson(parsed, (v) => {
        if (v === null || typeof v !== 'object' || Array.isArray(v) || !(drift.from in v)) return v;
        const out: Record<string, unknown> = {};
        for (const [k, x] of Object.entries(v)) out[k === drift.from ? drift.to : k] = x;
        return out;
      });
      break;
    case 'wrap':
      changed = { [drift.under]: parsed };
      break;
    case 'number_as_string':
      changed = mapJson(parsed, (v) => (typeof v === 'number' ? String(v) : v));
      break;
  }
  return JSON.stringify(changed);
}

/** The (original, stale) pairs of the lines a shell poison variant changes. */
export function staleLines(original: string, variant: string): Array<[string, string]> {
  const a = original.split('\n');
  const b = variant.split('\n');
  if (a.length !== b.length) return [];
  const pairs: Array<[string, string]> = [];
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i] && a[i] !== '') pairs.push([a[i]!, b[i]!]);
  return pairs;
}

// What `cat -n`, `grep -n` and `grep` over several files put before a line.
const LINE_PREFIX = /^(\s*\d+\t|\d+[:-]|[^\t\n]*?:(\d+[:-])?)$/;

/**
 * Shell poison delivery (D-0037): each output line that shows an original
 * changed line, whole or after a line-number or file-name prefix, shows the
 * stale line instead. Output that does not show those lines is unchanged.
 */
export function replaceStaleLines(output: string, pairs: ReadonlyArray<readonly [string, string]>): string {
  if (pairs.length === 0) return output;
  return output
    .split('\n')
    .map((line) => {
      const cr = line.endsWith('\r') ? '\r' : '';
      const body = cr ? line.slice(0, -1) : line;
      for (const [orig, stale] of pairs) {
        if (body === orig) return stale + cr;
        if (body.endsWith(orig) && LINE_PREFIX.test(body.slice(0, body.length - orig.length))) {
          return body.slice(0, body.length - orig.length) + stale + cr;
        }
      }
      return line;
    })
    .join('\n');
}
