import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
// @ts-expect-error plain ES module without type declarations
import { sources } from '../scripts/sync-data.mjs';

describe('data copied from outside packages/site', () => {
  const pairs = sources() as [string, string][];

  it('every copy equals its source (run `pnpm sync-data` after changing one)', () => {
    expect(pairs.length).toBeGreaterThan(0);
    for (const [from, to] of pairs) expect(readFileSync(to, 'utf8'), to).toBe(readFileSync(from, 'utf8'));
  });

  it('no copy is left without a source', () => {
    const expected = new Set(pairs.map(([, to]) => to));
    for (const dir of ['capabilities', 'smoke']) {
      for (const f of readdirSync(join(process.cwd(), 'data', dir))) {
        expect(expected.has(join(process.cwd(), 'data', dir, f)), f).toBe(true);
      }
    }
  });
});
