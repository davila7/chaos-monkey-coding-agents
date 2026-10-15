import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { z } from 'zod';

const count = z.number().int().nonnegative();
const usd = z.number().nonnegative();

export const SmokeProfile = z.object({
  trials: count,
  tasks: count,
  pass1: z.number().min(0).max(1),
  cost_usd_total: usd,
  cost_usd_mean: usd,
  faults_applied: count,
  eligible_calls_min: count,
  infra_failures: count,
  status: z.record(z.string(), count),
});
export type SmokeProfile = z.infer<typeof SmokeProfile>;

export const SmokeTrial = z.object({
  trial: z.string().min(1),
  task: z.string().min(1),
  profile: z.string().min(1),
  attempt: count,
  reward: z.number().nullable(),
  cost_usd: usd.nullable(),
  eligible_calls: count,
  faults: z.array(z.unknown()),
  infra_failure: z.string().nullable(),
  status: z.string().nullable(),
});
export type SmokeTrial = z.infer<typeof SmokeTrial>;

/** `cmca-trial-summary/1`, written by `cmca_analysis.trials`; only the fields the site shows are checked. */
export const SmokeSummary = z.object({
  schema: z.literal('cmca-trial-summary/1'),
  profiles: z.record(z.string(), SmokeProfile),
  trials: z.array(SmokeTrial),
});
export type SmokeSummary = z.infer<typeof SmokeSummary>;

export interface SmokeRun {
  /** File stem in data/smoke: a date, optionally followed by a slug (`2026-10-15-track-s`). */
  id: string;
  date: string;
  /** Repository path of the source the copy in data/smoke was made from. */
  source: string;
  summary: SmokeSummary;
}

const DIR = () => join(process.cwd(), 'data/smoke');
const RUN_FILE = /^(\d{4}-\d{2}-\d{2})(-[a-z0-9-]+)?\.json$/;

export function loadSmokeRun(id: string): SmokeRun {
  const summary = SmokeSummary.parse(JSON.parse(readFileSync(join(DIR(), `${id}.json`), 'utf8')));
  return { id, date: id.slice(0, 10), source: `results/smoke/${id}/summary.json`, summary };
}

/** Every committed run, newest first; runs on the same date sort by name. */
export function smokeRuns(): SmokeRun[] {
  const ids = readdirSync(DIR())
    .filter((f) => RUN_FILE.test(f))
    .map((f) => f.slice(0, -'.json'.length))
    .sort((a, b) => b.slice(0, 10).localeCompare(a.slice(0, 10)) || a.localeCompare(b));
  if (ids.length === 0) throw new Error('data/smoke has no run; run `pnpm sync-data`');
  return ids.map(loadSmokeRun);
}

export function callRange(trials: SmokeTrial[]): { min: number; max: number } {
  const calls = trials.map((t) => t.eligible_calls);
  return { min: Math.min(...calls), max: Math.max(...calls) };
}

export const totalFaults = (s: SmokeSummary) => Object.values(s.profiles).reduce((n, p) => n + p.faults_applied, 0);
