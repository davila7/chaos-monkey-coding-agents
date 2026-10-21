import { readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { createEngine } from '../src/engine.js';
import { loadHarnessConfig, loadProfile } from '../src/load.js';
import { MemorySink } from '../src/logger.js';
import { InjectionRecordSchema } from '../src/schemas.js';
import { MemoryStateStore, type StateStore } from '../src/state.js';
import { truncateHead30 } from '../src/transforms.js';
import { ROOT, catalog, config, profile, profileWith, sig } from './helpers.js';

const always = (over = {}) => profileWith(profile('moderate'), { base_rate: 1, max_applied_per_trial: 100, ...over });

describe('engine', () => {
  it('logs one valid record per eligible call, injected or not', () => {
    const sink = new MemorySink();
    const engine = createEngine({ config: config(), catalog, store: new MemoryStateStore(), sink });
    for (let i = 0; i < 50; i++) engine.evaluate(sig({ canonicalArgs: `${i}` }));
    expect(sink.records).toHaveLength(50);
    expect(sink.records.map((r) => r.seq)).toEqual([...Array(50).keys()]);
    for (const r of sink.records) InjectionRecordSchema.parse(r);
  });

  it('passes through and logs an error record when internals throw', () => {
    const sink = new MemorySink();
    const broken: StateStore = {
      transact() {
        throw new Error('disk full');
      },
    };
    const engine = createEngine({ config: config({ profile: always() }), catalog, store: broken, sink });
    const d = engine.evaluate(sig());
    expect(d.inject).toBe(false);
    expect(sink.records[0]).toMatchObject({ decision: 'error', seq: null, error: 'disk full' });
    InjectionRecordSchema.parse(sink.records[0]);
  });

  it('returns catalog text for message payloads', () => {
    const engine = createEngine({
      config: config({ profile: always({ weights: { deny: 1 } }) }),
      catalog,
      store: new MemoryStateStore(),
      sink: new MemorySink(),
    });
    const d = engine.evaluate(sig());
    expect(d.type).toBe('deny');
    expect(engine.payload(d)).toBe('EACCES: permission denied');
  });

  it('applies post-phase transforms', () => {
    const tool = 'mcp.docs.get_doc';
    const cfg = (weights: Record<string, number>) =>
      config({
        layer: 'service',
        profile: always({ weights }),
        task: {
          schema: 'tt-task/1',
          poison: [{ tool, match: {}, variant: 'v1.json', token: 'tok-abcdef' }],
          drift: [{ tool, kind: 'rename_key', from: 'results', to: 'items' }],
          non_idempotent: [{ tool }],
        },
        variants: { 'v1.json': '{"results":["stale tok-abcdef"]}' },
      });
    const out = '{"results":[1,2,3]}';
    const s = sig({ capability: tool, toolName: tool, args: {} });
    const mk = (w: Record<string, number>) =>
      createEngine({ config: cfg(w), catalog, store: new MemoryStateStore(), sink: new MemorySink() });
    const apply = (w: Record<string, number>) => {
      const e = mk(w);
      return e.applyOutput(e.evaluate(s), out);
    };
    expect(apply({ empty: 1 })).toBe('');
    expect(apply({ trunc: 1 })).toBe(truncateHead30(out));
    expect(apply({ poison: 1 })).toContain('tok-abcdef');
    expect(apply({ drift: 1 })).toBe('{"items":[1,2,3]}');
    expect(apply({ falsefail: 1 })).toMatch(/^(Error|504)/);
  });

  it('truncates to the first 30% by code points with no marker', () => {
    expect(truncateHead30('0123456789')).toBe('012');
    expect(truncateHead30('ééééééééé€')).toBe('ééé');
  });
});

describe('repository data files', () => {
  it('every profile parses and matches SPEC 6.3', () => {
    const expected: Record<string, [number, number]> = {
      clean: [0, 0],
      light: [0.05, 3],
      moderate: [0.15, 6],
      heavy: [0.3, 10],
      byzantine: [0.1, 4],
    };
    const files = readdirSync(`${ROOT}profiles`).filter((f) => f.endsWith('.yaml'));
    expect(files.sort()).toEqual(Object.keys(expected).map((n) => `${n}.yaml`).sort());
    for (const [name, [rate, cap]] of Object.entries(expected)) {
      const p = loadProfile(`${ROOT}profiles/${name}.yaml`);
      expect([p.name, p.base_rate, p.max_applied_per_trial]).toEqual([name, rate, cap]);
    }
  });

  it('every config parses', () => {
    const files = readdirSync(`${ROOT}configs`).filter((f) => f.endsWith('.yaml'));
    expect(files).toHaveLength(7);
    for (const f of files) expect(loadHarnessConfig(`${ROOT}configs/${f}`).id).toBe(f.replace('.yaml', ''));
  });
});
