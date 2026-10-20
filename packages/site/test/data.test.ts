import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadSiteData } from '../src/lib/data';
import { Interval, SiteData } from '../src/lib/schema';

afterEach(() => vi.restoreAllMocks());

describe('committed data files', () => {
  it('results.json is valid and is not sample data', () => {
    expect(loadSiteData('results.json').kind).not.toBe('sample');
  });

  it('sample.json is valid and marked as sample', () => {
    const d = loadSiteData('sample.json');
    expect(d.kind).toBe('sample');
    expect(d.boards.length).toBeGreaterThan(0);
  });

  it('sample.json uses no real harness or model names', () => {
    const d = loadSiteData('sample.json');
    for (const row of d.boards.flatMap((b) => b.rows)) {
      expect(row.harness.name).toMatch(/^Sample /);
      expect(row.model.id).toMatch(/^sample-/);
    }
  });
});

describe('analysis output', () => {
  it('the site data in the cmca_analysis release snapshot satisfies this schema', () => {
    const snapshot = join(process.cwd(), '../../python/cmca_analysis/tests/snapshots/release.json');
    const data = SiteData.parse(JSON.parse(readFileSync(snapshot, 'utf8')).site);
    expect(data.kind).toBe('release');
    expect(data.boards.map((b) => b.id)).toEqual(['track-s', 'track-n-fixed']);
    expect(data.not_measurable).toContainEqual(expect.objectContaining({ board: 'track-n-fixed', config_id: 'fx-claude' }));
  });
});

describe('loadSiteData', () => {
  it('refuses a results.json that carries sample data', () => {
    const dir = mkdtempSync(join(tmpdir(), 'site-'));
    mkdirSync(join(dir, 'data'));
    writeFileSync(
      join(dir, 'data/results.json'),
      JSON.stringify({ schema: 'site-data/1', kind: 'sample', release: null, generated_at: null, source: null, boards: [] }),
    );
    vi.spyOn(process, 'cwd').mockReturnValue(dir);
    expect(() => loadSiteData('results.json')).toThrow(/sample/);
  });
});

describe('Interval', () => {
  it('rejects a point estimate outside its interval', () => {
    expect(Interval.safeParse({ value: 0.5, lo: 0.6, hi: 0.7 }).success).toBe(false);
  });
});
