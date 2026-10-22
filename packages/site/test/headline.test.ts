import { describe, expect, it } from 'vitest';
import { loadSiteData } from '../src/lib/data';
import { headlineRanking } from '../src/lib/headline';
import { SiteData } from '../src/lib/schema';

const iv = { value: 0.5, lo: 0.4, hi: 0.6 };
const row = (name: string, succeeded: number | null, sent = 36) => ({
  config_id: `${name}-m`,
  harness: { name, version: '1' },
  model: { id: 'm', route: 'r', reasoning: null },
  axis: 'fixed',
  trials: 72,
  excluded: 0,
  metrics: { faulted_success: iv, clean_pass1: iv, rr: null, pass3_moderate: null, overclaim_rate: null, poison_propagation_rate: null, dollars_per_success: null, tokens_total: null },
  faulted_counts: succeeded === null ? null : { succeeded, sent },
  curve: null,
});
const data = (rows: unknown[], id = 'track-s') =>
  SiteData.parse({ schema: 'site-data/1', kind: 'release', release: 'r', generated_at: null, source: null, boards: [{ id, title: 't', description: '', rows }] });

describe('headlineRanking', () => {
  it('shares a rank on equal shares and skips the next places', () => {
    const r = headlineRanking(data([row('c', 21), row('b', 25), row('d', 24), row('a', 25)]));
    expect(r.map((x) => [x.rank, x.harness, x.succeeded])).toEqual([
      [1, 'a', 25],
      [1, 'b', 25],
      [3, 'd', 24],
      [4, 'c', 21],
    ]);
  });

  it('drops rows without counts and boards other than Track S', () => {
    expect(headlineRanking(data([row('a', null)]))).toEqual([]);
    expect(headlineRanking(data([row('a', 3)], 'track-n-fixed'))).toEqual([]);
  });

  it('ranks the committed release with counts that match Faulted Success', () => {
    const d = loadSiteData('results.json');
    const r = headlineRanking(d);
    expect(r.length).toBe(d.boards.find((b) => b.id === 'track-s')!.rows.length);
    for (const x of r) {
      const fs = d.boards.find((b) => b.id === 'track-s')!.rows.find((o) => o.harness.name === x.harness)!.metrics.faulted_success.value;
      expect(x.share).toBeCloseTo(fs, 3);
    }
  });
});
