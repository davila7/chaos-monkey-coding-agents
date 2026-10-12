import { describe, expect, it } from 'vitest';
import { callRange, latestSmokeRun, loadSmokeRun, SmokeSummary, totalFaults } from '../src/lib/smoke';

describe('committed smoke runs', () => {
  it('2026-10-11 parses and its profile counts match its trials', () => {
    const { summary } = loadSmokeRun('2026-10-11');
    for (const [name, p] of Object.entries(summary.profiles)) {
      expect(summary.trials.filter((t) => t.profile === name).length).toBe(p.trials);
    }
  });

  it('the latest run is the newest date in data/smoke', () => {
    expect(latestSmokeRun().date >= '2026-10-11').toBe(true);
  });
});

describe('helpers', () => {
  const trial = (eligible_calls: number) => ({
    trial: 't',
    task: 'x',
    profile: 'clean',
    attempt: 0,
    reward: 1,
    cost_usd: 0.01,
    eligible_calls,
    faults: [],
    infra_failure: null,
    status: 'success',
  });

  it('callRange returns min and max eligible calls', () => {
    expect(callRange([trial(4), trial(2), trial(3)])).toEqual({ min: 2, max: 4 });
  });

  it('totalFaults sums faults_applied over profiles', () => {
    const p = { trials: 1, tasks: 1, pass1: 1, cost_usd_total: 0, cost_usd_mean: 0, eligible_calls_min: 0, infra_failures: 0, status: {} };
    const s = SmokeSummary.parse({
      schema: 'cmca-trial-summary/1',
      profiles: { clean: { ...p, faults_applied: 0 }, moderate: { ...p, faults_applied: 3 } },
      trials: [],
    });
    expect(totalFaults(s)).toBe(3);
  });

  it('rejects another schema', () => {
    expect(SmokeSummary.safeParse({ schema: 'cmca-trial-summary/2', profiles: {}, trials: [] }).success).toBe(false);
  });
});
