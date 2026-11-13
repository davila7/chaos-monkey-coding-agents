import { readFileSync, writeFileSync } from 'node:fs';
import catalog from '../../catalog/v1.json' with { type: 'json' };
import { canonicalArgs } from '../canonical.js';
import { createEngine, type FaultEngine } from '../engine.js';
import { JsonlSink } from '../logger.js';
import type { CatalogEntry, EngineConfig, InjectionRecord } from '../schemas.js';
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
 * `--apply`: stdin `{ post, output, output_file? }`, stdout `{ output }`.
 * Applies a post-phase transform chosen by an earlier decide call. Never
 * reads or writes trial state and never logs; on any failure the output is
 * returned unchanged.
 *
 * With `output_file` (a harness file under `tool-results/` that holds the
 * full output, D-0054), the transform runs on that file's content and the
 * transformed text replaces the file, so the real output cannot be read back
 * from it. stdout then carries `file: "rewritten"`, or `file: "unread"` with
 * the stdin output unchanged when the file could not be read or written.
 */
function applyMain(raw: string): void {
  let output = '';
  let file: 'rewritten' | 'unread' | undefined;
  try {
    const p = JSON.parse(raw) as { post?: PostRef; output?: unknown; output_file?: unknown };
    output = typeof p.output === 'string' ? p.output : '';
    let path: string | undefined;
    if (p.output_file !== undefined) {
      file = 'unread';
      if (typeof p.output_file === 'string' && p.output_file.startsWith('/') && p.output_file.includes('/tool-results/')) {
        path = p.output_file;
      }
    }
    if (p.post && (p.output_file === undefined || path)) {
      const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8')) as EngineConfig;
      const engine = createEngine({
        config,
        catalog: catalog as CatalogEntry[],
        store: new MemoryStateStore(),
        sink: { write() {} },
      });
      const original = output;
      try {
        const full = path ? readFileSync(path, 'utf8') : output;
        const out = engine.applyOutput(fromPostRef(p.post), full);
        if (path) {
          writeFileSync(path, out);
          file = 'rewritten';
        }
        output = out;
      } catch {
        output = original;
      }
    }
  } catch {
    // pass the original output through
  }
  process.stdout.write(JSON.stringify(file ? { output, file } : { output }));
}

/**
 * `--undelivered`: stdin `{ post, tool_name, capability, reason }`, stdout
 * `{}`. Logs that an applied post-phase fault did not reach the model
 * because the call ended where the harness lets no hook replace the result
 * (D-0048). Writes only that record; trial state is untouched.
 */
function undeliveredMain(raw: string): void {
  try {
    const p = JSON.parse(raw) as { post?: PostRef; tool_name?: unknown; capability?: unknown; reason?: unknown };
    if (p.post && typeof p.post.type === 'string') {
      const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf8')) as Partial<EngineConfig>;
      const record: InjectionRecord = {
        schema: 'tt-event/2',
        seq: null,
        ts: new Date().toISOString(),
        trial_id: typeof config.trial_id === 'string' ? config.trial_id : null,
        task_id: typeof config.task_id === 'string' ? config.task_id : '',
        attempt: typeof config.attempt === 'number' ? config.attempt : 0,
        harness: typeof config.harness === 'string' ? config.harness : '',
        layer: config.layer === 'service' ? 'service' : 'native',
        tool_name: typeof p.tool_name === 'string' ? p.tool_name : '',
        capability: typeof p.capability === 'string' ? p.capability : '',
        args_hash: '',
        key: '',
        occurrence: 0,
        decision: 'undelivered',
        type: p.post.type,
        payload_id: p.post.payload_id ?? null,
        exempt_reason: null,
        agent_id: null,
        latency_ms: 0,
        persistence: null,
        of_seq: typeof p.post.seq === 'number' ? p.post.seq : null,
        reason: typeof p.reason === 'string' ? p.reason : null,
      };
      new JsonlSink(LOG_PATH).write(record);
    }
  } catch {
    // best effort, as for the setup error record
  }
  process.stdout.write('{}');
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
  if (process.argv.includes('--undelivered')) return undeliveredMain(readStdin());
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
