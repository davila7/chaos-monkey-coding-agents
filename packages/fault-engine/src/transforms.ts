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
