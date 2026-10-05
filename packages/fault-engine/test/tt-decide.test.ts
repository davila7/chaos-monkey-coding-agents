import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { beforeAll, describe, expect, it } from 'vitest';
import { InjectionRecordSchema } from '../src/schemas.js';
import { PKG, config, profile, profileWith } from './helpers.js';

const BIN = join(PKG, 'dist/bin/tt-decide.cjs');

beforeAll(() => {
  const r = spawnSync(process.execPath, ['scripts/bundle.mjs'], { cwd: PKG, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
});

function setup(over: Parameters<typeof config>[0] = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'tt-'));
  const cfgPath = join(dir, 'config.json');
  writeFileSync(cfgPath, JSON.stringify(config(over)));
  const env = { ...process.env, TT_CONFIG: cfgPath, TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };
  return { dir, env, log: env.TT_LOG };
}

function call(env: NodeJS.ProcessEnv, payload: unknown): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [BIN], { env });
    let out = '';
    child.stdout.on('data', (b) => (out += b));
    child.on('error', reject);
    child.on('close', () => resolve(out));
    child.stdin.end(JSON.stringify(payload));
  });
}

const readLog = (p: string) =>
  readFileSync(p, 'utf8')
    .trim()
    .split('\n')
    .map((l) => InjectionRecordSchema.parse(JSON.parse(l)));

describe('tt-decide', () => {
  it('holds the cap and a gap-free sequence under 32 concurrent invocations', async () => {
    const cap = 5;
    const { env, log } = setup({ profile: profileWith(profile('moderate'), { base_rate: 1, max_faults_per_trial: cap }) });
    const outs = await Promise.all(
      Array.from({ length: 32 }, (_, i) =>
        call(env, { tool_name: 'Read', capability: 'fs.read', args: { path: `/app/f${i}.txt` } }),
      ),
    );
    const parsed = outs.map((o) => JSON.parse(o) as { apply: boolean });
    expect(parsed.filter((o) => o.apply)).toHaveLength(cap);
    const records = readLog(log);
    expect(records).toHaveLength(32);
    expect(records.map((r) => r.seq).sort((a, b) => a! - b!)).toEqual([...Array(32).keys()]);
    expect(records.filter((r) => r.decision === 'inject')).toHaveLength(cap);
  });

  it('keeps per-key occurrence state across processes', async () => {
    const p = profileWith(profile('moderate'), { base_rate: 1, max_faults_per_trial: 10, persistence: { sticky_2: 1 } });
    const { env } = setup({ profile: p });
    const payload = { tool_name: 'Read', capability: 'fs.read', args: { path: 'a.txt' } };
    const seq: boolean[] = [];
    for (let i = 0; i < 3; i++) seq.push((JSON.parse(await call(env, payload)) as { apply: boolean }).apply);
    expect(seq).toEqual([true, true, false]);
  });

  it('passes through on a missing config or malformed input', async () => {
    const { env } = setup();
    expect(JSON.parse(await call({ ...env, TT_CONFIG: '/nonexistent' }, { tool_name: 'Read', capability: 'fs.read' }))).toEqual({ apply: false });
    const child = spawnSync(process.execPath, [BIN], { env, input: 'not json', encoding: 'utf8' });
    expect(child.status).toBe(0);
    expect(JSON.parse(child.stdout)).toEqual({ apply: false });
  });
});
