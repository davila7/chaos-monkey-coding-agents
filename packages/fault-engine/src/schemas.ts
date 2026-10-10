import { z } from 'zod';
import { FAULT_TYPES } from './types.js';

export const FaultTypeSchema = z.enum(FAULT_TYPES);

const rate = z.number().min(0).max(1);

export const CapabilityClassSchema = z
  .string()
  .regex(/^(fs\.(read|write|edit|search|list)|shell|mcp\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/);

/** `mcp` applies to every `mcp.<server>.<tool>` class. */
export const MultiplierKeySchema = z.enum([
  'shell',
  'fs.read',
  'fs.write',
  'fs.edit',
  'fs.search',
  'fs.list',
  'mcp',
]);

const persistenceKey = /^(transient|outage|sticky_[1-9][0-9]*)$/;

export const ProfileSchema = z
  .object({
    schema: z.literal('tt-profile/2'),
    name: z.string().regex(/^[a-z][a-z0-9-]*$/),
    base_rate: rate,
    max_applied_per_trial: z.number().int().min(0),
    warmup_calls: z.number().int().min(0).default(0),
    persistence: z.record(z.string().regex(persistenceKey), rate).default({}),
    outage_window: z.number().int().min(1).optional(),
    weights: z.partialRecord(FaultTypeSchema, z.number().min(0)).default({}),
    class_rate_multipliers: z.partialRecord(MultiplierKeySchema, z.number().min(0)).default({}),
  })
  .strict()
  .superRefine((p, ctx) => {
    if (p.base_rate === 0) return;
    const psum = Object.values(p.persistence).reduce((a, b) => a + b, 0);
    if (Math.abs(psum - 1) > 1e-9) {
      ctx.addIssue({ code: 'custom', message: `persistence weights sum to ${psum}, expected 1` });
    }
    const wsum = Object.values(p.weights).reduce<number>((a, b) => a + (b ?? 0), 0);
    if (Math.abs(wsum - 1) > 1e-9) {
      ctx.addIssue({ code: 'custom', message: `type weights sum to ${wsum}, expected 1` });
    }
    if ((p.persistence.outage ?? 0) > 0 && p.outage_window === undefined) {
      ctx.addIssue({ code: 'custom', message: 'outage persistence requires outage_window' });
    }
    if ((p.weights.byz ?? 0) > 0 && p.name !== 'byzantine') {
      ctx.addIssue({ code: 'custom', message: 'byz weight is only allowed in the byzantine profile' });
    }
  });
export type Profile = z.infer<typeof ProfileSchema>;

export const TransformSchema = z.enum([
  'empty',
  'truncate_head_30',
  'poison_variant',
  'drift_variant',
  'inarg_adapter',
  'byz_adapter',
  'delay',
]);

export const CatalogEntrySchema = z
  .object({
    id: z.string().regex(/^[a-z]+(\.[a-z0-9_]+)+$/),
    type: FaultTypeSchema,
    text: z.string(),
    applies_to: z.array(z.string().regex(/^(fs\.(read|write|edit|search|list)|shell|mcp\.\*|mcp\.[A-Za-z0-9_-]+\.(\*|[A-Za-z0-9_-]+))$/)).min(1),
    transform: TransformSchema.optional(),
  })
  .strict()
  .refine((e) => e.id.startsWith(`${e.type}.`), { message: 'id must start with "<type>."' });
export type CatalogEntry = z.infer<typeof CatalogEntrySchema>;

export const CatalogSchema = z
  .array(CatalogEntrySchema)
  .refine((c) => new Set(c.map((e) => e.id)).size === c.length, { message: 'duplicate entry id' });
export type Catalog = z.infer<typeof CatalogSchema>;

/** A tool reference in chaos.toml: a capability class or `mcp.<server>.<tool>`. */
const ToolRef = CapabilityClassSchema;

export const DriftSchema = z.discriminatedUnion('kind', [
  z.object({ tool: ToolRef, kind: z.literal('rename_key'), from: z.string(), to: z.string() }).strict(),
  z.object({ tool: ToolRef, kind: z.literal('wrap'), under: z.string() }).strict(),
  z.object({ tool: ToolRef, kind: z.literal('number_as_string') }).strict(),
]);
export type Drift = z.infer<typeof DriftSchema>;

export const TaskChaosSchema = z
  .object({
    schema: z.literal('tt-task/1'),
    exposure: z.object({ expected_classes: z.array(z.string()).default([]) }).strict().default({ expected_classes: [] }),
    poison: z
      .array(
        z
          .object({
            tool: ToolRef,
            match: z.record(z.string(), z.unknown()).default({}),
            variant: z.string(),
            token: z.string().min(6),
          })
          .strict(),
      )
      .default([]),
    non_idempotent: z.array(z.object({ tool: ToolRef }).strict()).default([]),
    drift: z.array(DriftSchema).default([]),
    alternatives: z.array(z.object({ tool: ToolRef, via: z.array(ToolRef).min(1) }).strict()).default([]),
    exempt: z.object({ paths: z.array(z.string()).default([]) }).strict().default({ paths: [] }),
  })
  .strict();
export type TaskChaos = z.infer<typeof TaskChaosSchema>;

/** Resolved runtime configuration handed to an injector or the proxy. */
export const EngineConfigSchema = z
  .object({
    schema: z.literal('tt-engine/1'),
    seed: z.string().min(1),
    trial_id: z.string().nullable().default(null),
    task_id: z.string().regex(/^[A-Za-z0-9._-]+$/),
    attempt: z.number().int().min(0),
    harness: z.string(),
    layer: z.enum(['service', 'native']),
    workspace_root: z.string().default('/app'),
    profile: ProfileSchema,
    parity_set: z.array(FaultTypeSchema),
    /**
     * (type, capability) cells conformance found undeliverable on this
     * harness version (D-0017). `capability` accepts the catalog's `mcp.*` form.
     */
    parity_gaps: z.array(z.object({ type: FaultTypeSchema, capability: z.string() }).strict()).default([]),
    catalog_version: z.string(),
    task: TaskChaosSchema,
    /** Path prefixes never faulted, in addition to the task's own exemptions. */
    exempt_paths: z.array(z.string()).default([]),
    /** Poison variant contents keyed by the `variant` reference in chaos.toml. */
    variants: z.record(z.string(), z.string()).default({}),
  })
  .strict();
export type EngineConfig = z.infer<typeof EngineConfigSchema>;
export type EngineConfigInput = z.input<typeof EngineConfigSchema>;

export const InjectionRecordSchema = z
  .object({
    schema: z.literal('tt-event/2'),
    seq: z.number().int().min(0).nullable(),
    ts: z.string(),
    trial_id: z.string().nullable(),
    task_id: z.string(),
    attempt: z.number().int().min(0),
    harness: z.string(),
    layer: z.enum(['service', 'native']),
    tool_name: z.string(),
    capability: z.string(),
    args_hash: z.string(),
    key: z.string(),
    occurrence: z.number().int().min(0),
    decision: z.enum(['apply', 'pass', 'error']),
    type: FaultTypeSchema.nullable(),
    payload_id: z.string().nullable(),
    exempt_reason: z.string().nullable(),
    agent_id: z.string().nullable(),
    latency_ms: z.number().min(0),
    persistence: z.enum(['transient', 'sticky', 'outage']).nullable().optional(),
    error: z.string().nullable().optional(),
  })
  .strict();
export type InjectionRecord = z.infer<typeof InjectionRecordSchema>;

export const HarnessConfigSchema = z
  .object({
    schema: z.literal('tt-config/1'),
    id: z.string().regex(/^[a-z0-9-]+$/),
    harness: z
      .object({
        name: z.string(),
        version: z.string(),
        harbor_agent: z.string().optional(),
      })
      .strict(),
    model: z.object({ id: z.string(), route: z.string(), reasoning: z.string() }).strict(),
    autonomy: z.object({ mode: z.literal('full'), native_setting: z.string() }).strict(),
    axes: z.array(z.enum(['native', 'fixed'])).min(1),
    tracks: z.array(z.enum(['s', 'n'])).min(1),
    limits: z
      .object({
        wall_clock_minutes: z.number().int().positive(),
        max_turns: z.union([z.number().int().positive(), z.string()]),
      })
      .strict(),
  })
  .strict();
export type HarnessConfig = z.infer<typeof HarnessConfigSchema>;

export const CapabilityFileSchema = z
  .object({
    schema: z.literal('tt-capabilities/1'),
    harness: z.string(),
    version: z.string(),
    generated_at: z.string(),
    tool_map: z.record(z.string(), z.string()),
    faults: z.partialRecord(
      FaultTypeSchema,
      z.union([
        z
          .object({
            supported: z.literal(true),
            delivered_as: z.string(),
            attribution_visible: z.boolean(),
            runs_passed: z.number().int().min(0),
          })
          .strict(),
        z.object({ supported: z.literal(false), reason: z.string() }).strict(),
      ]),
    ),
    crash_behavior: z.enum(['fail_open', 'fail_closed', 'unknown']),
    injector_p95_ms: z.number().min(0),
  })
  .strict();
export type CapabilityFile = z.infer<typeof CapabilityFileSchema>;

export const SubmissionMetadataSchema = z
  .object({
    schema: z.literal('cmca-submission/1'),
    release: z.string(),
    board: z.string(),
    config_id: z.string(),
    harness: z.object({ name: z.string(), version: z.string() }).strict(),
    model: z.object({ id: z.string(), route: z.string(), reasoning: z.string() }).strict(),
    permission_mode: z.string(),
    profiles: z.array(z.string()).min(1),
    attempts: z.number().int().positive(),
    seed: z.string(),
    harbor_version: z.string(),
    injector_build: z.string(),
    submitter: z.object({ name: z.string(), affiliation: z.string(), contact: z.string() }).strict(),
    deviations: z.string(),
    hub: z.object({ jobs: z.array(z.string()).min(1) }).strict(),
  })
  .strict();
export type SubmissionMetadata = z.infer<typeof SubmissionMetadataSchema>;

export const ALL_SCHEMAS = {
  'tt-profile-2': ProfileSchema,
  'tt-catalog-1': CatalogSchema,
  'tt-task-1': TaskChaosSchema,
  'tt-engine-1': EngineConfigSchema,
  'tt-event-2': InjectionRecordSchema,
  'tt-config-1': HarnessConfigSchema,
  'tt-capabilities-1': CapabilityFileSchema,
  'cmca-submission-1': SubmissionMetadataSchema,
} as const;
