import { appendFileSync, existsSync, mkdirSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { createEngine, JsonlSink, MemoryStateStore, resolveEngineConfig, type CatalogEntry } from '@cmca/fault-engine';
import catalog from '@cmca/fault-engine/catalog/v1.json' with { type: 'json' };
import { createProxy, DEFAULT_PAYLOAD_CAP } from '../proxy.js';

// TT_UPSTREAMS: "tickets=http://tickets-backend:8080/mcp,docs=http://docs-backend:8080/mcp"
const upstreams = Object.fromEntries(
  (process.env.TT_UPSTREAMS ?? '')
    .split(',')
    .filter(Boolean)
    .map((pair) => {
      const i = pair.indexOf('=');
      return [pair.slice(0, i), pair.slice(i + 1)];
    }),
);
const configPath = process.env.TT_CONFIG ?? '';
const logPath = process.env.TT_LOG ?? '/var/log/tt/events.jsonl';
const proxyLog = process.env.TT_PROXY_LOG ?? '/var/log/tt/gateway.jsonl';
const port = Number(process.env.PORT ?? '8000');
const cap = Number(process.env.TT_PAYLOAD_CAP ?? DEFAULT_PAYLOAD_CAP);

mkdirSync(dirname(proxyLog), { recursive: true });
const onEvent = (e: Record<string, unknown>) => appendFileSync(proxyLog, `${JSON.stringify(e)}\n`);

let engineOpts = {};
if (configPath && existsSync(configPath)) {
  const raw = JSON.parse(readFileSync(configPath, 'utf8'));
  const attempt = process.env.TT_ATTEMPT === undefined ? raw.attempt : Number(process.env.TT_ATTEMPT);
  const config = resolveEngineConfig({ ...raw, attempt, trial_id: process.env.TT_TRIAL_ID ?? raw.trial_id ?? null });
  if (config.layer !== 'service') throw new Error(`${configPath}: layer must be "service"`);
  const engine = createEngine({
    config,
    catalog: catalog as CatalogEntry[],
    store: new MemoryStateStore(),
    sink: new JsonlSink(logPath),
  });
  engineOpts = { engine, sig: { taskId: config.task_id, attempt: config.attempt, harness: config.harness } };
  onEvent({ ts: new Date().toISOString(), event: 'start', mode: 'engine', profile: config.profile.name, task: config.task_id, attempt: config.attempt });
} else {
  onEvent({ ts: new Date().toISOString(), event: 'start', mode: 'passthrough' });
}

createProxy({ upstreams, payloadCap: cap, onEvent, ...engineOpts }).listen(port, '0.0.0.0');
