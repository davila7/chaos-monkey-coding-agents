import type { Interval } from './schema';

/**
 * Rank bands (SPEC 12): configs whose 95% intervals for Faulted Success overlap share a band.
 * Overlap is not transitive, so rows are sorted by point estimate and a new band starts when a
 * row's interval no longer overlaps the interval of the first row in the current band.
 */
export function rankBands(items: Interval[]): number[] {
  const order = items.map((c, i) => ({ c, i })).sort((a, b) => b.c.value - a.c.value || a.i - b.i);
  const bands = new Array<number>(items.length);
  let band = 0;
  let head: Interval | undefined;
  for (const { c, i } of order) {
    if (!head || c.hi < head.lo) {
      band += 1;
      head = c;
    }
    bands[i] = band;
  }
  return bands;
}

/** Configs not dominated on (higher Faulted Success, lower dollars per success). */
export function paretoFront(points: { id: string; x: number; y: number }[]): string[] {
  const sorted = [...points].sort((a, b) => a.x - b.x || b.y - a.y);
  const front: string[] = [];
  let best = -Infinity;
  for (const p of sorted) {
    if (p.y > best) {
      front.push(p.id);
      best = p.y;
    }
  }
  return front;
}
