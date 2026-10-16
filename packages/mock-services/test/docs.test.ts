import { describe, expect, it } from 'vitest';
import { DocsStore, type DocsFixture } from '../src/index.js';

const fixture: DocsFixture = {
  schema: 'docs-fixture/1',
  docs: [
    { id: 'retry-policy', title: 'Retry policy', tags: ['api'], updated_at: '2026-09-01', body: 'Overview\nClients retry 429 responses after the Retry-After delay.' },
    { id: 'rate-limits', title: 'Rate limits', tags: ['api'], updated_at: '2026-09-02', body: 'Each key gets 60 requests per minute. A 429 means slow down.' },
    { id: 'oncall', title: 'On-call', tags: ['ops'], updated_at: '2026-09-03', body: 'Page the owner. ' + 'x'.repeat(300) },
    ...Array.from({ length: 6 }, (_, i) => ({ id: `note-${i}`, title: `Note ${i}`, tags: [], updated_at: '2026-09-04', body: 'misc 429' })),
  ],
};

describe('DocsStore', () => {
  it('ranks by matched words, then id, and paginates', () => {
    const s = new DocsStore(fixture);
    const r = s.search({ query: 'retry 429' });
    expect(r.results.map((d) => d.id)).toEqual(['retry-policy', 'note-0', 'note-1', 'note-2', 'note-3']);
    expect(r).toMatchObject({ total: 8, next_page: 2 });
    expect(r.results[0]).toMatchObject({ matched_terms: 2, snippet: 'Clients retry 429 responses after the Retry-After delay.' });
    expect(s.search({ query: '429', tag: 'api' }).results.map((d) => d.id)).toEqual(['rate-limits', 'retry-policy']);
  });

  it('cuts long snippets and serves full docs', () => {
    const s = new DocsStore(fixture);
    expect(s.search({ query: 'owner' }).results[0]!.snippet).toHaveLength(160);
    expect(s.doc('oncall').body).toHaveLength(316);
    expect(() => s.doc('missing')).toThrow(/404 Not Found/);
    expect(() => s.search({ query: '  ' })).toThrow(/400/);
  });
});
