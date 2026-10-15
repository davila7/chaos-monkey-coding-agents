import { z } from 'zod';

const unit = z.number().min(0).max(1);

/** Point estimate with a 95% hierarchical bootstrap interval (SPEC 12). */
export const Interval = z
  .object({ value: unit, lo: unit, hi: unit })
  .refine((c) => c.lo <= c.value && c.value <= c.hi, { message: 'interval must satisfy lo <= value <= hi' });
export type Interval = z.infer<typeof Interval>;

export const Row = z.object({
  config_id: z.string().min(1),
  harness: z.object({ name: z.string().min(1), version: z.string().min(1) }),
  model: z.object({ id: z.string().min(1), route: z.string().min(1), reasoning: z.string().nullable() }),
  axis: z.enum(['native', 'fixed']),
  trials: z.number().int().nonnegative(),
  excluded: z.number().int().nonnegative(),
  metrics: z.object({
    /** Headline: pass^1 under `moderate` (SPEC 11). */
    faulted_success: Interval,
    clean_pass1: Interval,
    /** Robustness Retention; can exceed 1, so it is not a unit interval. */
    rr: z.object({ value: z.number().nonnegative(), lo: z.number().nonnegative(), hi: z.number().nonnegative() }).nullable(),
    pass3_moderate: Interval.nullable(),
    overclaim_rate: Interval.nullable(),
    poison_propagation_rate: Interval.nullable(),
    dollars_per_success: z.number().nonnegative().nullable(),
    tokens_total: z.number().int().nonnegative().nullable(),
  }),
  /** pass^1 per fault profile base rate, for the degradation curve. */
  curve: z.array(z.object({ profile: z.string(), base_rate: unit, pass1: Interval })).nullable(),
  /** Committed job directories this row was computed from. */
  trial_links: z.array(z.string()).default([]),
});
export type Row = z.infer<typeof Row>;

export const Board = z.object({
  id: z.string().regex(/^[a-z0-9-]+$/),
  title: z.string().min(1),
  description: z.string(),
  rows: z.array(Row),
});
export type Board = z.infer<typeof Board>;

/** A config that belongs to a board's axis but cannot run on its track (D-0031 item 1). */
export const NotMeasurable = z.object({ board: z.string(), config_id: z.string(), reason: z.string().min(1) });
export type NotMeasurable = z.infer<typeof NotMeasurable>;

export const SiteData = z.object({
  schema: z.literal('site-data/1'),
  /**
   * `release`: benchmark results. `smoke`: pipeline check, shown without bands or comparison.
   * `sample`: invented numbers for previewing the layout; never a production build.
   */
  kind: z.enum(['release', 'smoke', 'sample']),
  release: z.string().nullable(),
  generated_at: z.string().nullable(),
  /** Commit and path of the analysis output the file was built from. */
  source: z.string().nullable(),
  boards: z.array(Board),
  not_measurable: z.array(NotMeasurable).default([]),
});
export type SiteData = z.infer<typeof SiteData>;
