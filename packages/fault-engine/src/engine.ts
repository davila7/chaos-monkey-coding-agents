import type { CatalogEntry, EngineConfig, InjectionRecord } from './schemas.js';
import { shortHash } from './hash.js';
import type { RecordSink } from './logger.js';
import { callKey, step } from './schedule.js';
import type { StateStore } from './state.js';
import { applyDrift, replaceStaleLines, staleLines, truncateHead30 } from './transforms.js';
import { FAULT_PHASE, type CallSignature, type FaultDecision } from './types.js';

export interface FaultEngine {
  /** Pure given persisted trial state. Updates the state store. */
  decide(sig: CallSignature): FaultDecision;
  /** Message text for message-style payloads; empty for transform payloads. */
  payload(decision: FaultDecision): string;
  log(record: InjectionRecord): void;
  /**
   * decide + log with the catch-all: any internal error yields a pass-through
   * decision and an `error` record, never an injected fault (SPEC 9.1).
   */
  evaluate(sig: CallSignature): FaultDecision;
  /** Output for a post-phase decision, given the real tool output. */
  applyOutput(decision: FaultDecision, output: string): string;
}

export interface EngineDeps {
  config: EngineConfig;
  catalog: readonly CatalogEntry[];
  store: StateStore;
  sink: RecordSink;
  now?: () => Date;
}

export function createEngine(deps: EngineDeps): FaultEngine {
  const { config, catalog, store, sink } = deps;
  const now = deps.now ?? (() => new Date());
  const byId = new Map(catalog.map((e) => [e.id, e]));

  const record = (
    sig: CallSignature,
    d: FaultDecision | null,
    latencyMs: number,
    error?: string,
  ): InjectionRecord => ({
    schema: 'tt-event/2',
    seq: d ? d.seq : null,
    ts: now().toISOString(),
    trial_id: config.trial_id,
    task_id: sig.taskId,
    attempt: sig.attempt,
    harness: sig.harness,
    layer: config.layer,
    tool_name: sig.toolName,
    capability: sig.capability,
    args_hash: shortHash(sig.canonicalArgs),
    key: d ? d.key : safeKey(sig),
    occurrence: d ? d.occurrence : 0,
    decision: error !== undefined ? 'error' : d?.inject ? 'apply' : 'pass',
    type: d?.type ?? null,
    payload_id: d?.payloadId ?? null,
    exempt_reason: d?.exemptReason ?? null,
    agent_id: sig.agentId ?? null,
    latency_ms: Math.round(latencyMs * 1000) / 1000,
    persistence: d?.persistence ?? null,
    ...(error !== undefined ? { error } : {}),
  });

  const safeKey = (sig: CallSignature): string => {
    try {
      return callKey(config, sig);
    } catch {
      return '';
    }
  };

  const engine: FaultEngine = {
    decide(sig) {
      return store.transact((state) => step(config, catalog, state, sig));
    },
    payload(d) {
      if (!d.inject || !d.payloadId) return '';
      return byId.get(d.payloadId)?.text ?? '';
    },
    log(r) {
      sink.write(r);
    },
    evaluate(sig) {
      const t0 = performance.now();
      let d: FaultDecision;
      try {
        d = engine.decide(sig);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        try {
          engine.log(record(sig, null, performance.now() - t0, msg));
        } catch {
          // logging is best effort on the error path
        }
        return { inject: false, key: '', occurrence: 0, seq: -1, exemptReason: 'error' };
      }
      try {
        engine.log(record(sig, d, performance.now() - t0));
      } catch {
        // a lost record is caught by sequence gap detection
      }
      return d;
    },
    applyOutput(d, output) {
      if (!d.inject || !d.type || FAULT_PHASE[d.type] !== 'post') return output;
      try {
        switch (d.type) {
          case 'empty':
            return '';
          case 'trunc':
            return truncateHead30(output);
          case 'falsefail':
            return engine.payload(d);
          case 'poison': {
            const decl = d.poisonIndex !== undefined ? config.task.poison[d.poisonIndex] : undefined;
            const content = decl ? config.variants[decl.variant] : undefined;
            if (decl?.source !== undefined) {
              const original = config.sources[decl.variant];
              return content !== undefined && original !== undefined
                ? replaceStaleLines(output, staleLines(original, content))
                : output;
            }
            return content ?? output;
          }
          case 'drift': {
            const decl = d.driftIndex !== undefined ? config.task.drift[d.driftIndex] : undefined;
            return (decl && applyDrift(output, decl)) ?? output;
          }
          default:
            return output;
        }
      } catch {
        return output;
      }
    },
  };
  return engine;
}
