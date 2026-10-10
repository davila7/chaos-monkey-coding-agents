import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { emptyState, step, type TrialState } from '../src/schedule.js';
import type { CapabilityClass } from '../src/types.js';
import { catalog, config, profile, profileWith, sig } from './helpers.js';

const capArb = fc.constantFrom<CapabilityClass>('fs.read', 'fs.write', 'fs.edit', 'fs.search', 'fs.list', 'shell');
const sigArb = fc.record({
  capability: capArb,
  canonicalArgs: fc.string({ maxLength: 40 }),
});

describe('SPEC 7.4 property 1: determinism', () => {
  it('same signature and same state give the same decision', () => {
    const cfg = config();
    fc.assert(
      fc.property(fc.array(sigArb, { maxLength: 30 }), sigArb, (history, probe) => {
        const state = emptyState();
        for (const h of history) step(cfg, catalog, state, sig(h));
        const a = structuredClone(state);
        const b = structuredClone(state);
        expect(step(cfg, catalog, a, sig(probe))).toEqual(step(cfg, catalog, b, sig(probe)));
        expect(a).toEqual(b);
      }),
      { numRuns: 300 },
    );
  });
});

describe('SPEC 7.4 property 2: observed rate', () => {
  for (const rate of [0.05, 0.15, 0.3]) {
    it(`is within 0.5 points of ${rate} over 100,000 signatures`, () => {
      const p = profileWith(profile('moderate'), { base_rate: rate, max_applied_per_trial: 1e9 });
      const cfg = config({ profile: p });
      const state = emptyState();
      let injected = 0;
      const N = 100_000;
      for (let i = 0; i < N; i++) {
        if (step(cfg, catalog, state, sig({ canonicalArgs: `{"path":"f/${i}"}` })).inject) injected++;
      }
      expect(Math.abs(injected / N - rate)).toBeLessThan(0.005);
    });
  }
});

describe('SPEC 7.4 property 3: caps', () => {
  it('never exceeds max_applied_per_trial, including persisted streaks', () => {
    fc.assert(
      fc.property(
        fc.array(sigArb, { minLength: 1, maxLength: 200 }),
        fc.integer({ min: 0, max: 8 }),
        fc.constantFrom('light', 'moderate', 'heavy'),
        (calls, cap, name) => {
          const p = profileWith(profile(name), { base_rate: 0.6, max_applied_per_trial: cap });
          const cfg = config({ profile: p });
          const state = emptyState();
          let n = 0;
          for (const c of calls) {
            // repeat each call to exercise sticky streaks
            for (let r = 0; r < 3; r++) if (step(cfg, catalog, state, sig(c)).inject) n++;
          }
          expect(n).toBeLessThanOrEqual(cap);
          expect(state.faults).toBe(n);
        },
      ),
      { numRuns: 300 },
    );
  });
});

describe('SPEC 7.4 property 4: independence from cross-key ordering', () => {
  it('per-key decisions do not depend on the interleaving of other keys', () => {
    const p = profileWith(profile('moderate'), { base_rate: 0.5, max_applied_per_trial: 1e9 });
    const cfg = config({ profile: p });
    const project = (state: TrialState, calls: { capability: CapabilityClass; canonicalArgs: string }[]) => {
      const out = new Map<string, string[]>();
      for (const c of calls) {
        const d = step(cfg, catalog, state, sig(c));
        const list = out.get(d.key) ?? [];
        list.push(`${d.occurrence}:${d.inject}:${d.type ?? ''}:${d.payloadId ?? ''}`);
        out.set(d.key, list);
      }
      return out;
    };
    fc.assert(
      fc.property(
        fc.array(sigArb, { minLength: 1, maxLength: 40 }).chain((calls) =>
          fc.tuple(fc.constant(calls), fc.shuffledSubarray(calls, { minLength: calls.length, maxLength: calls.length })),
        ),
        ([calls, shuffled]) => {
          expect(project(emptyState(), shuffled)).toEqual(project(emptyState(), calls));
        },
      ),
      { numRuns: 300 },
    );
  });
});
