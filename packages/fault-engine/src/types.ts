export type CapabilityClass =
  | 'fs.read'
  | 'fs.write'
  | 'fs.edit'
  | 'fs.search'
  | 'fs.list'
  | 'shell'
  | `mcp.${string}.${string}`;

export const FAULT_TYPES = [
  'deny',
  'err',
  'inarg',
  'empty',
  'trunc',
  'falsefail',
  'poison',
  'drift',
  'latency',
  'rate',
  'byz',
] as const;

export type FaultType = (typeof FAULT_TYPES)[number];

export type Layer = 'service' | 'native';

export type Phase = 'pre' | 'post';

export const FAULT_PHASE: Record<FaultType, Phase> = {
  deny: 'pre',
  err: 'pre',
  inarg: 'pre',
  empty: 'post',
  trunc: 'post',
  falsefail: 'post',
  poison: 'post',
  drift: 'post',
  latency: 'pre',
  rate: 'pre',
  byz: 'post',
};

/** Layers on which each type may be applied (SPEC 7.1). */
export const FAULT_LAYERS: Record<FaultType, readonly Layer[]> = {
  deny: ['service', 'native'],
  err: ['service', 'native'],
  inarg: ['native'],
  empty: ['service', 'native'],
  trunc: ['service', 'native'],
  falsefail: ['service', 'native'],
  poison: ['service', 'native'],
  drift: ['service'],
  latency: ['service'],
  rate: ['service'],
  byz: ['native'],
};

/** `stale`: a targeted poison that holds for every matching call of the trial (D-0037). */
export type PersistenceMode = 'transient' | 'sticky' | 'outage' | 'stale';

/** Types a profile may draw once per trial instead of per call (D-0037). */
export const TARGETED_TYPES = ['poison', 'falsefail'] as const;
export type TargetedType = (typeof TARGETED_TYPES)[number];

export interface CallSignature {
  taskId: string;
  attempt: number;
  harness: string;
  toolName: string;
  capability: CapabilityClass;
  canonicalArgs: string;
  agentId?: string;
  /** Raw arguments, used only to match task declarations (poison `match`). */
  args?: unknown;
  /** Absolute paths the call touches, used for path exemptions. */
  paths?: string[];
}

export interface FaultDecision {
  inject: boolean;
  type?: FaultType;
  payloadId?: string;
  key: string;
  occurrence: number;
  seq: number;
  exemptReason?: string;
  persistence?: PersistenceMode;
  /** Present for `latency`. Deterministic, 2 to 20 seconds. */
  delayMs?: number;
  /** Present for `poison`: index into the task's poison declarations. */
  poisonIndex?: number;
  /** Present for `drift`: index into the task's drift declarations. */
  driftIndex?: number;
}
