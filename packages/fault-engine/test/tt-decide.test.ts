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
    expect(records.filter((r) => r.decision === 'apply')).toHaveLength(cap);
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

describe('tt-decide setup failures', () => {
  it('logs an error record for an unresolved config instead of passing silently', async () => {
    const { dir, env, log } = setup();
    const raw = { ...config(), task: { schema: 'tt-task/1' } } as Record<string, unknown>;
    delete raw.workspace_root;
    writeFileSync(join(dir, 'config.json'), JSON.stringify(raw));
    const out = JSON.parse(await call(env, { tool_name: 'Read', capability: 'fs.read', args: { file_path: '/app/x' } }));
    expect(out).toEqual({ apply: false });
    const [rec] = readLog(log);
    expect(rec).toMatchObject({ decision: 'error', tool_name: 'Read', capability: 'fs.read', seq: null });
    expect(rec!.error).toMatch(/not resolved; missing workspace_root, task.exposure/);
  });

  it('logs an error record when the config file is missing', async () => {
    const { env, log } = setup();
    await call({ ...env, TT_CONFIG: '/nonexistent' }, { tool_name: 'Bash', capability: 'shell', args: { command: 'ls' } });
    expect(readLog(log)[0]).toMatchObject({ decision: 'error', task_id: '' });
  });
});

describe('tt-decide --apply', () => {
  const apply = (env: NodeJS.ProcessEnv, payload: unknown) =>
    JSON.parse(spawnSync(process.execPath, [BIN, '--apply'], { env, input: JSON.stringify(payload), encoding: 'utf8' }).stdout) as {
      output: string;
    };

  it('returns a post reference that --apply turns into the transformed output', async () => {
    const p = profileWith(profile('moderate'), {
      base_rate: 1,
      max_faults_per_trial: 10,
      weights: { trunc: 1 },
      persistence: { transient: 1 },
    });
    const { env, log } = setup({ profile: p });
    const out = JSON.parse(await call(env, { tool_name: 'Bash', capability: 'shell', args: { command: 'ls' } })) as {
      apply: boolean;
      phase: string;
      post: unknown;
    };
    expect(out).toMatchObject({ apply: true, phase: 'post', post: { type: 'trunc' } });
    const before = readFileSync(log, 'utf8');
    expect(apply(env, { post: out.post, output: '0123456789' }).output).toBe('012');
    expect(readFileSync(log, 'utf8')).toBe(before);
  });

  it('passes the output through on a missing reference or bad input', () => {
    const { env } = setup();
    expect(apply(env, { output: 'abc' }).output).toBe('abc');
    const r = spawnSync(process.execPath, [BIN, '--apply'], { env, input: 'nope', encoding: 'utf8' });
    expect(JSON.parse(r.stdout)).toEqual({ output: '' });
  });
});
