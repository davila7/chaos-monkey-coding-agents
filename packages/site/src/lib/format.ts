import type { Interval } from './schema';

export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;

/** Half-width of the interval in percentage points, as "± x.x". */
export const halfWidth = (c: Interval) => `± ${(((c.hi - c.lo) / 2) * 100).toFixed(1)}`;

export function compact(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return String(n);
}

export const dollars = (n: number) => (n >= 100 ? `$${n.toFixed(0)}` : `$${n.toFixed(2)}`);

/** Four decimals: smoke and pilot trials cost cents, which `dollars` would round away. */
export const usd = (n: number) => `$${n.toFixed(4)}`;
