import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import { capabilityOf, install, pathsOf, type Api, type Run, type ToolCallEvent, type ToolResultEvent } from '../src/index.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');

beforeAll(() => {
  const r = spawnSync(process.execPath, ['scripts/bundle.mjs'], { cwd: ENGINE, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
});

function setup(weights: Record<string, number>) {
  const dir = mkdtempSync(join(tmpdir(), 'pi-'));
  const cfg = resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 's',
    task_id: 'probe',
    attempt: 0,
    harness: 'pi',
    layer: 'native',
    profile: { schema: 'tt-profile/2', name: 'probe', base_rate: 1, max_applied_per_trial: 100, persistence: { transient: 1 }, weights },
    parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'],
    catalog_version: 'v1',
    task: { schema: 'tt-task/1' },
  } as EngineConfigInput);
  writeFileSync(join(dir, 'config.json'), JSON.stringify(cfg));
  const env = { ...process.env, TT_CONFIG: join(dir, 'config.json'), TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };
  const run: Run = async (args, stdin) => {
    const r = spawnSync(process.execPath, [BIN, ...args], { env, input: stdin, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
    return r.stdout;
  };
  const handlers: Record<string, (e: never, ctx: { cwd: string }) => Promise<unknown>> = {};
  const pi = { on: (name: string, h: never) => void (handlers[name] = h) } as unknown as Api;
  install(pi, run);
  const ctx = { cwd: '/app' };
  return {
    log: env.TT_LOG,
    call: (e: ToolCallEvent) => handlers.tool_call!(e as never, ctx),
    result: (e: ToolResultEvent) => handlers.tool_result!(e as never, ctx),
  };
}

const bash = (id: string): ToolCallEvent => ({ toolName: 'bash', toolCallId: id, input: { command: 'ls' } });
const text = (t: string) => [{ type: 'text', text: t }];

describe('mapping', () => {
  it('maps Pi tools and resolves relative paths', () => {
    expect(capabilityOf('find')).toBe('fs.search');
    expect(capabilityOf('ls')).toBe('fs.list');
    expect(capabilityOf('todo')).toBeNull();
    expect(pathsOf({ path: 'src/a.ts' }, '/app')).toEqual(['/app/src/a.ts']);
    expect(pathsOf({ command: 'ls' }, '/app')).toEqual([]);
  });
});

describe('handlers with the real engine', () => {
  it('blocks pre-phase faults', async () => {
    const h = setup({ err: 1 });
    const out = (await h.call(bash('1'))) as { block: boolean; reason: string };
    expect(out.block).toBe(true);
    expect(out.reason.length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(h.log, 'utf8'))).toMatchObject({ decision: 'apply', harness: 'pi', tool_name: 'bash' });
  });

  it('truncates a post-phase result and its structured output', async () => {
    const h = setup({ trunc: 1 });
    expect(await h.call(bash('2'))).toBeUndefined();
    const patch = await h.result({
      ...bash('2'),
      content: text('0123456789'),
      structuredContent: { output: '0123456789', truncated: false },
      isError: false,
    });
    expect(patch).toEqual({ content: text('012'), structuredContent: { output: '012', truncated: false } });
  });

  it('marks a falsefail result as an error after the call ran', async () => {
    const h = setup({ falsefail: 1 });
    const e: ToolCallEvent = { toolName: 'write', toolCallId: '3', input: { path: 'a.txt', content: 'x' } };
    await h.call(e);
    const patch = (await h.result({ ...e, content: text('ok'), isError: false })) as { isError: boolean; content: { text: string }[] };
    expect(patch.isError).toBe(true);
    expect(patch.content[0]!.text).toMatch(/ECONNRESET/);
  });

  it('leaves results of unfaulted or errored calls alone', async () => {
    const h = setup({ trunc: 1 });
    expect(await h.result({ ...bash('none'), content: text('x'), isError: false })).toBeUndefined();
    await h.call(bash('4'));
    expect(await h.result({ ...bash('4'), content: text('boom'), isError: true })).toBeUndefined();
  });

  it('never faults exempt paths', async () => {
    const h = setup({ deny: 1 });
    expect(await h.call({ toolName: 'read', toolCallId: '5', input: { path: '/logs/agent/x' } })).toBeUndefined();
  });

  it('passes through when tt-decide fails, since a throw would block the tool', async () => {
    const handlers: Record<string, (e: unknown, c: unknown) => Promise<unknown>> = {};
    install({ on: (n: string, f: never) => void (handlers[n] = f) } as unknown as Api, async () => {
      throw new Error('spawn failed');
    });
    expect(await handlers.tool_call!(bash('6'), { cwd: '/app' })).toBeUndefined();
  });
});
