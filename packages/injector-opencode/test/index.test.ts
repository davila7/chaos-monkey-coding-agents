import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import { capabilityOf, hooks, pathsOf, type AfterOutput, type Run } from '../src/index.js';
import plugin from '../src/plugin.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');

beforeAll(() => {
  const r = spawnSync(process.execPath, ['scripts/bundle.mjs'], { cwd: ENGINE, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
});

function setup(weights: Record<string, number>, failing = false) {
  const dir = mkdtempSync(join(tmpdir(), 'oc-'));
  const cfg = resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 's',
    task_id: 'probe',
    attempt: 0,
    harness: 'opencode',
    layer: 'native',
    profile: { schema: 'tt-profile/2', name: 'probe', base_rate: 1, max_applied_per_trial: 100, persistence: { transient: 1 }, weights },
    parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'],
    catalog_version: 'v1',
    task: { schema: 'tt-task/1' },
  } as EngineConfigInput);
  writeFileSync(join(dir, 'config.json'), JSON.stringify(cfg));
  const env = { ...process.env, TT_CONFIG: join(dir, 'config.json'), TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };
  const run: Run = async (args, stdin) => {
    if (failing) throw new Error('spawn node ENOENT');
    const r = spawnSync(process.execPath, [BIN, ...args], { env, input: stdin, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
    return r.stdout;
  };
  return { log: env.TT_LOG, h: hooks('/app', run) };
}

const call = (id: string, tool = 'bash') => ({ tool, sessionID: 's', callID: id });
const result = (output: string): AfterOutput => ({ title: 't', output, metadata: {} });

describe('mapping', () => {
  it('maps OpenCode tools and resolves relative paths', () => {
    expect(capabilityOf('glob')).toBe('fs.search');
    expect(capabilityOf('list')).toBe('fs.list');
    expect(capabilityOf('todowrite')).toBeNull();
    expect(pathsOf({ filePath: '/app/a.ts' }, '/app')).toEqual(['/app/a.ts']);
    expect(pathsOf({ pattern: 'x', path: 'src' }, '/app')).toEqual(['/app/src']);
    expect(pathsOf({ command: 'ls' }, '/app')).toEqual([]);
  });

  it('exports only the plugin from the entry module', () => {
    expect(plugin.id).toBe('tt-runtime');
    expect(typeof plugin.server).toBe('function');
  });
});

describe('hooks with the real engine', () => {
  it('refuses pre-phase faults by throwing the catalog text', async () => {
    const { h, log } = setup({ err: 1 });
    const err = await h['tool.execute.before'](call('1'), { args: { command: 'ls' } }).catch((e: Error) => e);
    expect(err).toBeInstanceOf(Error);
    expect((err as Error).message.length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(log, 'utf8'))).toMatchObject({ decision: 'apply', harness: 'opencode', tool_name: 'bash' });
  });

  it('truncates the output of a post-phase fault', async () => {
    const { h } = setup({ trunc: 1 });
    await h['tool.execute.before'](call('2'), { args: { command: 'ls' } });
    const out = result('0123456789');
    await h['tool.execute.after']({ ...call('2'), args: {} }, out);
    expect(out.output).toBe('012');
  });

  it('reports a failure after the call ran for falsefail', async () => {
    const { h } = setup({ falsefail: 1 });
    await h['tool.execute.before'](call('3', 'write'), { args: { filePath: '/app/x', content: 'a' } });
    await expect(h['tool.execute.after']({ ...call('3', 'write'), args: {} }, result('Wrote file'))).rejects.toThrow(/./);
  });

  it('leaves unmapped tools and other calls alone', async () => {
    const { h, log } = setup({ err: 1 });
    await h['tool.execute.before'](call('4', 'todowrite'), { args: {} });
    const out = result('same');
    await h['tool.execute.after']({ ...call('5'), args: {} }, out);
    expect(out.output).toBe('same');
    expect(() => readFileSync(log, 'utf8')).toThrow();
  });

  it('passes calls through when the engine cannot run', async () => {
    const { h } = setup({ err: 1 }, true);
    await expect(h['tool.execute.before'](call('6'), { args: { command: 'ls' } })).resolves.toBeUndefined();
  });
});
