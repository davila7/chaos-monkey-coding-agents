// Measures end-to-end tt-decide invocation latency (process start to exit),
// the cost a command-style adapter pays per tool call. SPEC 9.1: p95 < 150 ms.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { performance } from 'node:perf_hooks';
import { parse } from 'yaml';
import { readFileSync } from 'node:fs';

const RUNS = Number(process.env.BENCH_RUNS ?? 100);
const BUDGET_MS = 150;
const bin = new URL('../dist/bin/tt-decide.cjs', import.meta.url).pathname;
const profile = parse(readFileSync(new URL('../../../profiles/moderate.yaml', import.meta.url), 'utf8'));

const dir = mkdtempSync(join(tmpdir(), 'tt-bench-'));
const cfgPath = join(dir, 'config.json');
writeFileSync(
  cfgPath,
  JSON.stringify({
    schema: 'tt-engine/1',
    seed: 'bench',
    trial_id: null,
    task_id: 'bench',
    attempt: 0,
    harness: 'bench',
    layer: 'native',
    workspace_root: '/app',
    profile,
    parity_set: ['deny', 'err', 'inarg', 'empty', 'trunc', 'falsefail', 'poison'],
    catalog_version: 'v1',
    task: { schema: 'tt-task/1', exposure: { expected_classes: [] }, poison: [], non_idempotent: [], drift: [], alternatives: [], exempt: { paths: [] } },
    exempt_paths: [],
    variants: {},
  }),
);
const env = { ...process.env, TT_CONFIG: cfgPath, TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };

const samples = [];
for (let i = 0; i < RUNS; i++) {
  const input = JSON.stringify({ tool_name: 'Read', capability: 'fs.read', args: { path: `/app/src/f${i % 40}.ts` } });
  const t0 = performance.now();
  const r = spawnSync(process.execPath, [bin], { env, input, encoding: 'utf8' });
  samples.push(performance.now() - t0);
  if (r.status !== 0) throw new Error(`tt-decide exited ${r.status}: ${r.stderr}`);
}
samples.sort((a, b) => a - b);
const q = (p) => samples[Math.min(samples.length - 1, Math.ceil(p * samples.length) - 1)];
const result = { runs: RUNS, p50_ms: +q(0.5).toFixed(1), p95_ms: +q(0.95).toFixed(1), max_ms: +samples.at(-1).toFixed(1), budget_ms: BUDGET_MS };
console.log(JSON.stringify(result));
if (result.p95_ms >= BUDGET_MS) process.exit(1);
