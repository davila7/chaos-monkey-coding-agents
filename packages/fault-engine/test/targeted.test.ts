import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { createEngine } from '../src/engine.js';
import { commandNamesPath, emptyState, step, targetedSelected } from '../src/schedule.js';
import { MemoryStateStore } from '../src/state.js';
import { replaceStaleLines, staleLines } from '../src/transforms.js';
import type { EngineConfigInput } from '../src/schemas.js';
import { catalog, config, profile, profileWith, sig } from './helpers.js';

const ORIGINAL = 'host = db-a\nport = 5432\nregion = west\n';
const VARIANT = 'host = db-a\nport = 6543 # tok-123456\nregion = west\n';

const shellPoison = (targeted: Record<string, number>, over: Partial<EngineConfigInput> = {}) =>
  config({
    profile: profileWith(profile('moderate'), { base_rate: 0, targeted }),
    task: {
      schema: 'tt-task/1',
      poison: [{ tool: 'shell', source: '/app/conf/db.conf', variant: 'variants/db.conf', token: 'tok-123456' }],
    },
    variants: { 'variants/db.conf': VARIANT },
    sources: { 'variants/db.conf': ORIGINAL },
    ...over,
  });

const shell = (command: string, attempt = 0) =>
  sig({ toolName: 'Bash', capability: 'shell', canonicalArgs: command, args: { command }, attempt });

describe('shell poison matching', () => {
  it('matches the source path absolute or relative to the workspace, as a whole path', () => {
    const yes = ['cat /app/conf/db.conf', 'cat conf/db.conf', 'head -5 ./conf/db.conf', "grep port 'conf/db.conf'", 'cat a conf/db.conf|wc'];
    const no = ['cat conf/db.conf.bak', 'cat other/conf/db.conf', 'cat /app/conf/db.confx', 'ls conf', 'cat /app/conf/db.conf~'];
    for (const c of yes) expect(commandNamesPath(c, '/app/conf/db.conf', '/app'), c).toBe(true);
    for (const c of no) expect(commandNamesPath(c, '/app/conf/db.conf', '/app'), c).toBe(false);
  });

  it('never rewrites the command', () => {
    const cfg = shellPoison({ poison: 1 });
    const args = { command: 'cat conf/db.conf' };
    const before = structuredClone(args);
    const d = step(cfg, catalog, emptyState(), sig({ capability: 'shell', canonicalArgs: args.command, args }));
    expect(d.type).toBe('poison');
    expect(args).toEqual(before);
  });
});

describe('stale line delivery', () => {
  const pairs = staleLines(ORIGINAL, VARIANT);

  it('replaces only the changed lines, also after cat -n and grep prefixes', () => {
    expect(pairs).toEqual([['port = 5432', 'port = 6543 # tok-123456']]);
    expect(replaceStaleLines(ORIGINAL, pairs)).toBe(VARIANT);
    expect(replaceStaleLines('     2\tport = 5432', pairs)).toBe('     2\tport = 6543 # tok-123456');
    expect(replaceStaleLines('2:port = 5432', pairs)).toBe('2:port = 6543 # tok-123456');
    expect(replaceStaleLines('conf/db.conf:2:port = 5432\r', pairs)).toBe('conf/db.conf:2:port = 6543 # tok-123456\r');
  });

  it('leaves output that does not show the lines unchanged', () => {
    expect(replaceStaleLines('3\n', pairs)).toBe('3\n');
    expect(replaceStaleLines('xport = 5432 extra', pairs)).toBe('xport = 5432 extra');
  });

  it('yields no pairs when line counts differ', () => {
    expect(staleLines(ORIGINAL, `${VARIANT}extra\n`)).toEqual([]);
  });

  it('is applied by the engine for shell declarations', () => {
    const cfg = shellPoison({ poison: 1 });
    const engine = createEngine({ config: cfg, catalog, store: new MemoryStateStore(), sink: { write() {} } });
    const d = engine.decide(shell('cat conf/db.conf'));
    expect(engine.applyOutput(d, ORIGINAL)).toBe(VARIANT);
  });
});

describe('targeted faults (D-0037)', () => {
  it('poisons every matching call of a selected trial, counted once against the cap', () => {
    const cfg = shellPoison({ poison: 1 });
    const state = emptyState();
    const ds = ['cat conf/db.conf', 'grep port conf/db.conf', 'cat conf/db.conf'].map((c) => step(cfg, catalog, state, shell(c)));
    expect(ds.every((d) => d.inject && d.type === 'poison' && d.persistence === 'stale' && d.poisonIndex === 0)).toBe(true);
    expect(state.faults).toBe(1);
    expect(step(cfg, catalog, state, shell('ls conf')).inject).toBe(false);
  });

  it('never applies at rate 0 and skips a capped trial', () => {
    expect(step(shellPoison({}), catalog, emptyState(), shell('cat conf/db.conf')).inject).toBe(false);
    const capped = shellPoison({ poison: 1 }, { profile: profileWith(profile('moderate'), { base_rate: 0, targeted: { poison: 1 }, max_applied_per_trial: 0 }) });
    const state = emptyState();
    expect(step(capped, catalog, state, shell('cat conf/db.conf')).exemptReason).toBe('cap');
    expect(step(capped, catalog, state, shell('cat conf/db.conf')).inject).toBe(false);
  });

  it('keeps cap room for a selected target, so per-call faults never crowd it out', () => {
    const p = profileWith(profile('heavy'), { base_rate: 1, max_applied_per_trial: 2, targeted: { poison: 1 } });
    const cfg = shellPoison({}, { profile: p });
    const state = emptyState();
    const early = ['ls a', 'ls b', 'ls c'].map((c) => step(cfg, catalog, state, shell(c)).inject);
    expect(early).toEqual([true, false, false]);
    expect(step(cfg, catalog, state, shell('cat conf/db.conf')).type).toBe('poison');
    expect(state.faults).toBe(2);
  });

  it('respects parity gaps', () => {
    const cfg = shellPoison({ poison: 1 }, { parity_gaps: [{ type: 'poison', capability: 'shell' }] });
    expect(step(cfg, catalog, emptyState(), shell('cat conf/db.conf')).inject).toBe(false);
  });

  it('does not depend on call order', () => {
    const cfg = shellPoison({ poison: 0.5 });
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 1000 }), fc.array(fc.constantFrom('ls', 'pwd', 'cat x', 'echo 1'), { maxLength: 10 }), (attempt, noise) => {
        const a = emptyState();
        const first = step(cfg, catalog, a, shell('cat conf/db.conf', attempt)).inject;
        const b = emptyState();
        for (const n of noise) step(cfg, catalog, b, shell(n, attempt));
        const later = step(cfg, catalog, b, shell('cat conf/db.conf', attempt)).type === 'poison';
        expect(later).toBe(first);
      }),
      { numRuns: 200 },
    );
  });

  for (const rate of [0.5, 1]) {
    it(`selects trials within 0.5 points of ${rate} over 100,000 trials`, () => {
      const cfg = shellPoison({ poison: rate });
      let n = 0;
      const N = 100_000;
      for (let i = 0; i < N; i++) if (targetedSelected(cfg, shell('cat conf/db.conf', i), 'poison', 0)) n++;
      expect(Math.abs(n / N - rate)).toBeLessThan(0.005);
    });
  }

  it('reports a false failure on the first call to a selected non-idempotent tool only, service layer', () => {
    const task = { schema: 'tt-task/1' as const, non_idempotent: [{ tool: 'mcp.svc.write_item' }] };
    const call = sig({ toolName: 'write_item', capability: 'mcp.svc.write_item', canonicalArgs: '{"id":1}' });
    const svc = config({ layer: 'service', profile: profileWith(profile('moderate'), { base_rate: 0, targeted: { falsefail: 1 } }), task });
    const state = emptyState();
    const first = step(svc, catalog, state, call);
    expect(first.type).toBe('falsefail');
    expect(step(svc, catalog, state, { ...call, canonicalArgs: '{"id":2}' }).inject).toBe(false);
    const native = config({ profile: profileWith(profile('moderate'), { base_rate: 0, targeted: { falsefail: 1 } }), task });
    expect(step(native, catalog, emptyState(), call).inject).toBe(false);
  });
});
