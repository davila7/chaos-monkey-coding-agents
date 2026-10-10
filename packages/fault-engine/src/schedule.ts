import type { CatalogEntry, EngineConfig, Profile } from './schemas.js';
import { shortHash, unitDraw } from './hash.js';
import {
  FAULT_LAYERS,
  FAULT_TYPES,
  type CallSignature,
  type FaultDecision,
  type FaultType,
  type PersistenceMode,
} from './types.js';

export interface KeyState {
  type: FaultType;
  payloadId: string;
  mode: PersistenceMode;
  /** Further consecutive occurrences that still fail. */
  remaining: number;
  poisonIndex?: number;
  driftIndex?: number;
  delayMs?: number;
}

export interface OutageState extends KeyState {
  tool: string;
}

export interface TrialState {
  v: 1;
  seq: number;
  eligible: number;
  faults: number;
  occ: Record<string, number>;
  keys: Record<string, KeyState>;
  outage: OutageState | null;
}

export function emptyState(): TrialState {
  return { v: 1, seq: 0, eligible: 0, faults: 0, occ: {}, keys: {}, outage: null };
}

export function callKey(cfg: Pick<EngineConfig, 'seed'>, sig: CallSignature): string {
  return shortHash([cfg.seed, sig.taskId, sig.attempt, sig.capability, sig.canonicalArgs].join('|'));
}

export function classRate(profile: Profile, capability: string): number {
  const mkey = capability.startsWith('mcp.') ? 'mcp' : capability;
  const mult = profile.class_rate_multipliers[mkey as keyof Profile['class_rate_multipliers']] ?? 1;
  return Math.min(1, profile.base_rate * mult);
}

export function appliesTo(pattern: string, capability: string): boolean {
  if (pattern === capability) return true;
  if (pattern.endsWith('.*')) return capability.startsWith(pattern.slice(0, -1));
  return false;
}

function matchesArgs(match: Record<string, unknown>, args: unknown): boolean {
  const keys = Object.keys(match);
  if (keys.length === 0) return true;
  if (args === null || typeof args !== 'object') return false;
  const a = args as Record<string, unknown>;
  return keys.every((k) => JSON.stringify(a[k]) === JSON.stringify(match[k]));
}

function isExemptPath(paths: readonly string[] | undefined, prefixes: readonly string[]): boolean {
  if (!paths) return false;
  return paths.some((p) => prefixes.some((pre) => p === pre || p.startsWith(pre.endsWith('/') ? pre : `${pre}/`)));
}

/** SPEC 7.6 default exemptions. Harness and injector directories are added by adapters. */
export const DEFAULT_EXEMPT_PATHS = ['/app/STATUS.json', '/tests', '/solution', '/logs', '/opt/tt'] as const;

interface Candidate {
  type: FaultType;
  weight: number;
  entries: CatalogEntry[];
  poisonIdx: number[];
  driftIdx: number[];
}

export function candidateTypes(cfg: EngineConfig, catalog: readonly CatalogEntry[], sig: CallSignature): Candidate[] {
  const parity = new Set(cfg.parity_set);
  const tool = sig.capability;
  const out: Candidate[] = [];
  for (const type of FAULT_TYPES) {
    const weight = cfg.profile.weights[type] ?? 0;
    if (weight <= 0 || !parity.has(type)) continue;
    if (cfg.parity_gaps.some((g) => g.type === type && appliesTo(g.capability, tool))) continue;
    if (!FAULT_LAYERS[type].includes(cfg.layer)) continue;
    if (type === 'byz' && cfg.profile.name !== 'byzantine') continue;
    if (type === 'falsefail' && cfg.layer === 'service' && !cfg.task.non_idempotent.some((n) => n.tool === tool)) continue;
    const poisonIdx: number[] = [];
    const driftIdx: number[] = [];
    if (type === 'poison') {
      cfg.task.poison.forEach((p, i) => {
        if (p.tool === tool && matchesArgs(p.match, sig.args)) poisonIdx.push(i);
      });
      if (poisonIdx.length === 0) continue;
    }
    if (type === 'drift') {
      cfg.task.drift.forEach((d, i) => {
        if (d.tool === tool) driftIdx.push(i);
      });
      if (driftIdx.length === 0) continue;
    }
    const entries = catalog
      .filter((e) => e.type === type && e.applies_to.some((p) => appliesTo(p, sig.capability)))
      .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    if (entries.length === 0) continue;
    out.push({ type, weight, entries, poisonIdx, driftIdx });
  }
  return out;
}

function pick<T>(items: readonly T[], u: number): T {
  return items[Math.min(items.length - 1, Math.floor(u * items.length))] as T;
}

function weighted<T extends { weight: number }>(items: readonly T[], u: number): T {
  const total = items.reduce((a, b) => a + b.weight, 0);
  let acc = 0;
  for (const it of items) {
    acc += it.weight / total;
    if (u < acc) return it;
  }
  return items[items.length - 1] as T;
}

function choosePersistence(
  cfg: EngineConfig,
  sig: CallSignature,
  u: number,
): { mode: PersistenceMode; extra: number } {
  const allowOutage =
    cfg.layer === 'service' &&
    cfg.profile.outage_window !== undefined &&
    cfg.task.alternatives.some((a) => a.tool === sig.capability);
  const options: { mode: PersistenceMode; extra: number; weight: number }[] = [];
  for (const [name, weight] of Object.entries(cfg.profile.persistence).sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (weight <= 0) continue;
    if (name === 'transient') options.push({ mode: 'transient', extra: 0, weight });
    else if (name === 'outage') {
      if (allowOutage) options.push({ mode: 'outage', extra: (cfg.profile.outage_window ?? 1) - 1, weight });
    } else {
      const k = Number(name.slice('sticky_'.length));
      options.push({ mode: 'sticky', extra: k - 1, weight });
    }
  }
  if (options.length === 0) return { mode: 'transient', extra: 0 };
  const chosen = weighted(options, u);
  return { mode: chosen.mode, extra: chosen.extra };
}

function fromKeyState(ks: KeyState): Partial<FaultDecision> {
  const d: Partial<FaultDecision> = { inject: true, type: ks.type, payloadId: ks.payloadId, persistence: ks.mode };
  if (ks.poisonIndex !== undefined) d.poisonIndex = ks.poisonIndex;
  if (ks.driftIndex !== undefined) d.driftIndex = ks.driftIndex;
  if (ks.delayMs !== undefined) d.delayMs = ks.delayMs;
  return d;
}

/**
 * The SPEC 7.4 decision function. Mutates `state` (occurrence counters,
 * sequence, fault count, persistence) and returns the decision. Given the
 * same state and signature it always returns the same decision.
 */
export function step(
  cfg: EngineConfig,
  catalog: readonly CatalogEntry[],
  state: TrialState,
  sig: CallSignature,
): FaultDecision {
  const key = callKey(cfg, sig);
  const occurrence = state.occ[key] ?? 0;
  state.occ[key] = occurrence + 1;
  const seq = state.seq++;
  const eligibleIndex = state.eligible++;
  const base = { key, occurrence, seq };
  const cap = cfg.profile.max_applied_per_trial;

  const priorOutage = state.outage;
  const tickOutage = () => {
    if (priorOutage && state.outage === priorOutage) {
      priorOutage.remaining -= 1;
      if (priorOutage.remaining <= 0) state.outage = null;
    }
  };
  const pass = (exemptReason?: string): FaultDecision => {
    tickOutage();
    return exemptReason === undefined ? { inject: false, ...base } : { inject: false, ...base, exemptReason };
  };

  const prefixes = [...DEFAULT_EXEMPT_PATHS, ...cfg.exempt_paths, ...cfg.task.exempt.paths];
  if (isExemptPath(sig.paths, prefixes)) return pass('exempt_path');
  if (eligibleIndex < cfg.profile.warmup_calls) return pass('warmup');

  if (priorOutage && priorOutage.remaining > 0 && priorOutage.tool === sig.capability) {
    if (state.faults >= cap) return pass('cap');
    state.faults += 1;
    tickOutage();
    return { ...base, ...fromKeyState(priorOutage), inject: true };
  }

  const ks = state.keys[key];
  if (ks) {
    if (ks.remaining <= 0) return pass();
    if (state.faults >= cap) {
      ks.remaining = 0;
      return pass('cap');
    }
    ks.remaining -= 1;
    state.faults += 1;
    tickOutage();
    return { ...base, ...fromKeyState(ks), inject: true };
  }

  const candidates = candidateTypes(cfg, catalog, sig);
  if (candidates.length === 0) return pass('not_applicable');
  const u = unitDraw(`${key}|${occurrence}`);
  if (!(u < classRate(cfg.profile, sig.capability))) return pass();
  if (state.faults >= cap) return pass('cap');

  const chosen = weighted(candidates, unitDraw(`${key}|${occurrence}|type`));
  const entry = pick(chosen.entries, unitDraw(`${key}|${occurrence}|payload`));
  const persistence = choosePersistence(cfg, sig, unitDraw(`${key}|${occurrence}|persistence`));
  const next: KeyState = { type: chosen.type, payloadId: entry.id, mode: persistence.mode, remaining: 0 };
  if (chosen.type === 'poison') next.poisonIndex = pick(chosen.poisonIdx, unitDraw(`${key}|${occurrence}|poison`));
  if (chosen.type === 'drift') next.driftIndex = pick(chosen.driftIdx, unitDraw(`${key}|${occurrence}|drift`));
  if (chosen.type === 'latency') next.delayMs = 2000 + Math.floor(unitDraw(`${key}|${occurrence}|delay`) * 18001);

  state.faults += 1;
  tickOutage();
  if (persistence.mode === 'outage') {
    state.keys[key] = next;
    if (persistence.extra > 0) state.outage = { ...next, tool: sig.capability, remaining: persistence.extra };
  } else {
    state.keys[key] = { ...next, remaining: persistence.extra };
  }
  return { ...base, ...fromKeyState(next), inject: true };
}
