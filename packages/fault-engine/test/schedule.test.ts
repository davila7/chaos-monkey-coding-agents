import { describe, expect, it } from 'vitest';
import { candidateTypes, emptyState, step } from '../src/schedule.js';
import { FAULT_TYPES, type CallSignature } from '../src/types.js';
import { catalog, config, profile, profileWith, sig } from './helpers.js';

const always = (name = 'moderate', over = {}) =>
  profileWith(profile(name), { base_rate: 1, max_faults_per_trial: 100, ...over });

function run(cfg: ReturnType<typeof config>, s: CallSignature, times: number) {
  const state = emptyState();
  return Array.from({ length: times }, () => step(cfg, catalog, state, s));
}

describe('persistence', () => {
  it('transient fails the first occurrence of a key only', () => {
    const cfg = config({ profile: always('light') });
    const ds = run(cfg, sig(), 4);
    expect(ds.map((d) => d.inject)).toEqual([true, false, false, false]);
    expect(ds.map((d) => d.occurrence)).toEqual([0, 1, 2, 3]);
  });

  it('sticky(2) fails two consecutive occurrences with the same payload', () => {
    const p = always('moderate', { persistence: { sticky_2: 1 } });
    const ds = run(config({ profile: p }), sig(), 4);
    expect(ds.map((d) => d.inject)).toEqual([true, true, false, false]);
    expect(ds[1]?.payloadId).toBe(ds[0]?.payloadId);
    expect(ds.every((d) => d.persistence === undefined || d.persistence === 'sticky')).toBe(true);
  });

  it('outage fails every call to one declared tool for w eligible calls, service layer only', () => {
    const tool = 'mcp.docs.search_docs';
    const p = always('heavy', { persistence: { outage: 1 }, outage_window: 3, weights: { err: 1 } });
    const task = { schema: 'tt-task/1' as const, alternatives: [{ tool, via: ['mcp.docs.get_doc'] }] };
    const cfg = config({ layer: 'service', profile: p, task, parity_set: ['err'] });
    const state = emptyState();
    const a = (q: string) => step(cfg, catalog, state, sig({ capability: tool, toolName: tool, canonicalArgs: q }));
    const first = a('{"q":"x"}');
    expect(first).toMatchObject({ inject: true, persistence: 'outage' });
    // Different arguments, same tool: still failing within the window.
    expect(a('{"q":"y"}')).toMatchObject({ inject: true, persistence: 'outage' });
    expect(a('{"q":"z"}')).toMatchObject({ inject: true, persistence: 'outage' });
    // Window of 3 eligible calls is over; "w" is a fresh key and draws again.
    expect(state.outage).toBeNull();

    const native = config({ layer: 'native', profile: p, task, parity_set: ['err'] });
    expect(step(native, catalog, emptyState(), sig()).persistence).toBe('transient');
  });
});

describe('exemptions', () => {
  it('never faults exempt paths', () => {
    const cfg = config({ profile: always() });
    for (const p of ['/app/STATUS.json', '/tests/test.sh', '/logs/agent/x', '/opt/tt/config.json', '/solution/solve.sh']) {
      const d = step(cfg, catalog, emptyState(), sig({ paths: [p] }));
      expect(d).toMatchObject({ inject: false, exemptReason: 'exempt_path' });
    }
    expect(step(cfg, catalog, emptyState(), sig({ paths: ['/app/STATUS.json.bak'] })).inject).toBe(true);
  });

  it('honors warmup_calls', () => {
    const cfg = config({ profile: always('moderate', { warmup_calls: 2 }) });
    const state = emptyState();
    const ds = ['a', 'b', 'c'].map((x) => step(cfg, catalog, state, sig({ canonicalArgs: x })));
    expect(ds.map((d) => d.exemptReason ?? null)).toEqual(['warmup', 'warmup', null]);
    expect(ds[2]?.inject).toBe(true);
  });

  it('clean never faults', () => {
    const cfg = config({ profile: profile('clean') });
    const state = emptyState();
    for (let i = 0; i < 1000; i++) expect(step(cfg, catalog, state, sig({ canonicalArgs: `${i}` })).inject).toBe(false);
  });
});

describe('type eligibility', () => {
  const types = (cfg: ReturnType<typeof config>, s: CallSignature) => candidateTypes(cfg, catalog, s).map((c) => c.type);

  it('never corrupts shell or write arguments', () => {
    const p = always('moderate', { weights: { inarg: 1 } });
    const cfg = config({ profile: p });
    expect(types(cfg, sig({ capability: 'shell' }))).not.toContain('inarg');
    expect(types(cfg, sig({ capability: 'fs.write' }))).not.toContain('inarg');
    expect(types(cfg, sig({ capability: 'fs.edit' }))).toContain('inarg');
  });

  it('allows byz only in the byzantine profile', () => {
    expect(types(config({ profile: profile('byzantine') }), sig({ capability: 'fs.write' }))).toEqual(['byz']);
    const forged = profileWith(profile('moderate'), { weights: { byz: 1 } });
    expect(() => config({ profile: forged })).toThrow(/byzantine/);
    // The engine refuses it even when schema validation is bypassed.
    expect(types({ ...config(), profile: forged }, sig({ capability: 'fs.write' }))).toEqual([]);
  });

  it('applies falsefail on the service layer only to non-idempotent tools', () => {
    const create = 'mcp.tickets.create_ticket';
    const get = 'mcp.tickets.get_ticket';
    const task = { schema: 'tt-task/1' as const, non_idempotent: [{ tool: create }] };
    const cfg = config({ layer: 'service', task });
    expect(types(cfg, sig({ capability: create }))).toContain('falsefail');
    expect(types(cfg, sig({ capability: get }))).not.toContain('falsefail');
  });

  it('applies poison only to declared, matching resources', () => {
    const tool = 'mcp.docs.get_doc';
    const task = {
      schema: 'tt-task/1' as const,
      poison: [{ tool, match: { doc_id: 'runbook' }, variant: 'v/runbook.json', token: 'tok-123456' }],
    };
    const cfg = config({ layer: 'service', task });
    expect(types(cfg, sig({ capability: tool, args: { doc_id: 'runbook' } }))).toContain('poison');
    expect(types(cfg, sig({ capability: tool, args: { doc_id: 'other' } }))).not.toContain('poison');
  });

  it('restricts types to the parity set and the layer', () => {
    const cfg = config({ parity_set: ['deny'] });
    expect(types(cfg, sig())).toEqual(['deny']);
    const native = config({ profile: always('moderate') });
    for (const t of types(native, sig({ capability: 'mcp.a.b' }))) {
      expect(['latency', 'rate', 'drift']).not.toContain(t);
    }
  });

  it('every type in the catalog has at least one entry', () => {
    for (const t of FAULT_TYPES) expect(catalog.some((e) => e.type === t)).toBe(true);
  });
});

describe('latency', () => {
  it('draws a delay between 2 and 20 seconds', () => {
    const p = always('moderate', { weights: { latency: 1 }, max_faults_per_trial: 1e9 });
    const cfg = config({ layer: 'service', profile: p });
    const state = emptyState();
    for (let i = 0; i < 500; i++) {
      const d = step(cfg, catalog, state, sig({ capability: 'mcp.a.b', canonicalArgs: `${i}` }));
      expect(d.delayMs).toBeGreaterThanOrEqual(2000);
      expect(d.delayMs).toBeLessThanOrEqual(20000);
    }
  });
});
