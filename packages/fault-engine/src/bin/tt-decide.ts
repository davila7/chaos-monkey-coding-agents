import { readFileSync } from 'node:fs';
import catalog from '../../catalog/v1.json' with { type: 'json' };
import { canonicalArgs } from '../canonical.js';
import { createEngine, type FaultEngine } from '../engine.js';
import { JsonlSink } from '../logger.js';
import type { CatalogEntry, EngineConfig } from '../schemas.js';
import { FileStateStore, MemoryStateStore } from '../state.js';
import type { CapabilityClass, FaultDecision } from '../types.js';
import { adapters, fromPostRef, type DecideRequest, type PostRef } from './adapters.js';
import { missingResolvedKeys } from './resolved.js';

const env = process.env;
const CONFIG_PATH = env.TT_CONFIG ?? '/opt/tt/config.json';
const STATE_DIR = env.TT_STATE ?? '/opt/tt/state';
const LOG_PATH = env.TT_LOG ?? '/logs/agent/tt/events.jsonl';

function formatArg(argv: readonly string[]): string {
  const i = argv.indexOf('--format');
  return i >= 0 ? (argv[i + 1] ?? 'generic') : 'generic';
}

function readStdin(): string {
  try {
    return readFileSync(0, 'utf8');
  } catch {
    return '';
  }
}

/**
 * `--apply`: stdin `{ post, output }`, stdout `{ output }`. Applies a
 * post-phase transform chosen by an earlier decide call. Never reads or
 * writes trial state and never logs; on any failure the output is returned
 * unchanged.
 */
function applyMain(raw: string): void {
  let output = '';
  try {
    const p = JSON.parse(raw) as { post?: PostRef; output?: unknown };
    output = typeof p.output === 'string' ? p.output : '';
    if (p.post) {
      const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8')) as EngineConfig;
      const engine = createEngine({
        config,
        catalog: catalog as CatalogEntry[],
        store: new MemoryStateStore(),
        sink: { write() {} },
      });
      output = engine.applyOutput(fromPostRef(p.post), output);
    }
  } catch {
    // pass the original output through
  }
  process.stdout.write(JSON.stringify({ output }));
}

/**
 * Records a failure that happened before the engine could log its own
 * record, so a broken setup shows up as `decision: "error"` instead of a
 * clean-looking trial.
 */
function logSetupError(raw: Partial<EngineConfig> | null, req: DecideRequest | null, message: string): void {
  try {
    const record = {
      schema: 'tt-event/2',
      seq: null,
      ts: new Date().toISOString(),
      trial_id: typeof raw?.trial_id === 'string' ? raw.trial_id : null,
      task_id: typeof raw?.task_id === 'string' ? raw.task_id : '',
      attempt: typeof raw?.attempt === 'number' ? raw.attempt : 0,
      harness: typeof raw?.harness === 'string' ? raw.harness : '',
      layer: raw?.layer === 'service' ? 'service' : 'native',
      tool_name: req?.toolName ?? '',
      capability: req?.capability ?? '',
      args_hash: '',
      key: '',
      occurrence: 0,
      decision: 'error',
      type: null,
      payload_id: null,
      exempt_reason: null,
      agent_id: req?.agentId ?? null,
      latency_ms: 0,
      persistence: null,
      error: message,
    };
    new JsonlSink(LOG_PATH).write(record as Parameters<JsonlSink['write']>[0]);
  } catch {
    // nothing left to report to
  }
}

function main(): void {
  if (process.argv.includes('--apply')) return applyMain(readStdin());
  const adapter = adapters[formatArg(process.argv.slice(2))] ?? adapters.generic!;
  const raw = readStdin();
  let engine: FaultEngine | null = null;
  let req: DecideRequest | null = null;
  let config: EngineConfig | null = null;
  let decision: FaultDecision | null = null;
  try {
    req = adapter.parse(raw);
    config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8')) as EngineConfig;
    const missing = missingResolvedKeys(config);
    if (missing.length > 0) throw new Error(`config is not resolved; missing ${missing.join(', ')}`);
    if (req) {
      engine = createEngine({
        config,
        catalog: catalog as CatalogEntry[],
        store: new FileStateStore(STATE_DIR),
        sink: new JsonlSink(LOG_PATH),
      });
      decision = engine.evaluate({
        taskId: config.task_id,
        attempt: config.attempt,
        harness: config.harness,
        toolName: req.toolName,
        capability: req.capability as CapabilityClass,
        canonicalArgs: canonicalArgs(req.capability as CapabilityClass, req.args, {
          workspaceRoot: config.workspace_root,
        }),
        args: req.args,
        ...(req.paths ? { paths: req.paths } : {}),
        ...(req.agentId ? { agentId: req.agentId } : {}),
      });
    }
  } catch (e) {
    decision = null;
    engine = null;
    if (req) logSetupError(config, req, e instanceof Error ? e.message : String(e));
  }
  let out: string;
  try {
    out = adapter.respond(decision && engine ? { decision, text: engine.payload(decision) } : null);
  } catch {
    out = adapter.respond(null);
  }
  process.stdout.write(out);
}

main();
