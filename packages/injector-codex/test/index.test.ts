import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import {
  capabilityOf,
  encode,
  filePending,
  handle,
  pathsOf,
  shellText,
  tokenCount,
  transcriptLookup,
  type CallEvent,
  type Finished,
  type Run,
} from '../src/index.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');
const PKG = resolve(import.meta.dirname, '..');

beforeAll(() => {
  // build.mjs deletes dist first, and the cli lint test reads dist while the
  // workspace tests run in parallel, so only build when `pnpm build` has not.
  const steps: [string, string][] = [[ENGINE, 'scripts/bundle.mjs']];
  if (!existsSync(join(PKG, 'dist/tt/codex/index.cjs'))) steps.push([PKG, 'scripts/build.mjs']);
  for (const [cwd, script] of steps) {
    const r = spawnSync(process.execPath, [script], { cwd, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
  }
});

const ORIGINAL = 'host = db-a\nport = 5432\nregion = west\n';
const VARIANT = 'host = db-a\nport = 6543 # tok-123456\nregion = west\n';

function setup(profile: { weights?: Record<string, number>; targeted?: Record<string, number>; base_rate?: number }) {
  const dir = mkdtempSync(join(tmpdir(), 'codex-'));
  const cfg = resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 's',
    task_id: 'probe',
    attempt: 0,
    harness: 'codex',
    layer: 'native',
    profile: {
      schema: 'tt-profile/2',
      name: 'probe',
      base_rate: profile.base_rate ?? 1,
      max_applied_per_trial: 100,
      persistence: { transient: 1 },
      weights: profile.weights ?? { err: 1 },
      ...(profile.targeted ? { targeted: profile.targeted } : {}),
    },
    parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'],
    catalog_version: 'v1',
    task: {
      schema: 'tt-task/1',
      poison: [{ tool: 'shell', source: '/app/conf/db.conf', variant: 'variants/db.conf', token: 'tok-123456' }],
    },
    variants: { 'variants/db.conf': VARIANT },
    sources: { 'variants/db.conf': ORIGINAL },
  } as EngineConfigInput);
  writeFileSync(join(dir, 'config.json'), JSON.stringify(cfg));
  const env = { ...process.env, TT_CONFIG: join(dir, 'config.json'), TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };
  const run: Run = async (args, stdin) => {
    const r = spawnSync(process.execPath, [BIN, ...args], { env, input: stdin, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
    return r.stdout;
  };
  const pending = filePending(join(dir, 'state', 'pending'));
  const finished = new Map<string, Finished>();
  const lookup = (_: string, id: string) => finished.get(id) ?? null;
  return { dir, env, log: env.TT_LOG, finished, go: (e: CallEvent) => handle(e, run, pending, lookup) };
}

const PATCH_EDIT = '*** Begin Patch\n*** Update File: conf/db.conf\n@@\n-port = 5432\n+port = 5433\n*** End Patch\n';
const PATCH_ADD = '*** Begin Patch\n*** Add File: notes/new.txt\n+hi\n*** End Patch\n';
const PATCH_OK = 'Exit code: 0\nWall time: 0 seconds\nOutput:\nSuccess. Updated the following files:\nM conf/db.conf\n';

const pre = (tool: string, input: Record<string, unknown>, id = 'call_1'): CallEvent => ({
  hook_event_name: 'PreToolUse',
  cwd: '/app',
  tool_name: tool,
  tool_input: input,
  tool_use_id: id,
  transcript_path: '/tmp/rollout.jsonl',
});
const post = (e: CallEvent, response: string): CallEvent => ({ ...e, hook_event_name: 'PostToolUse', tool_response: response });

describe('mapping', () => {
  it('maps Bash to shell and apply_patch to fs.write or fs.edit by its hunks', () => {
    expect(capabilityOf('Bash', { command: 'ls' })).toBe('shell');
    expect(capabilityOf('apply_patch', { command: PATCH_ADD })).toBe('fs.write');
    expect(capabilityOf('apply_patch', { command: PATCH_EDIT })).toBe('fs.edit');
    expect(capabilityOf('apply_patch', { command: PATCH_ADD + PATCH_EDIT })).toBe('fs.edit');
    expect(capabilityOf('mcp__tickets__list_open', {})).toBeNull();
    expect(capabilityOf('view_image', {})).toBeNull();
    expect(pathsOf('apply_patch', { command: PATCH_EDIT }, '/app')).toEqual(['/app/conf/db.conf']);
    expect(pathsOf('Bash', { command: 'cat conf/db.conf' }, '/app')).toEqual([]);
  });
});

describe('shell text', () => {
  it('counts tokens as Codex does for its header', () => {
    expect(tokenCount('hello\n')).toBe(2);
    expect(tokenCount("ls: cannot access 'nope': No such file or directory\n")).toBe(13);
    expect(tokenCount('')).toBe(0);
  });

  it('rebuilds the header Codex shows for a finished command', () => {
    const text = shellText('call_1', { exitCode: 2, seconds: 0.00012 }, 'x\n');
    expect(text).toMatch(/^Chunk ID: [0-9a-f]{6}\nWall time: 0\.0001 seconds\nProcess exited with code 2\nOriginal token count: 1\nOutput:\nx\n$/);
    expect(shellText('call_1', { exitCode: 2, seconds: 0.00012 }, 'x\n')).toBe(text);
  });

  it('reads the exit code and duration from the rollout transcript', () => {
    const dir = mkdtempSync(join(tmpdir(), 'codex-'));
    const path = join(dir, 'rollout.jsonl');
    const item = (id: string, exit: number) =>
      JSON.stringify({
        type: 'event_msg',
        payload: { type: 'item_completed', item: { type: 'CommandExecution', id, exit_code: exit, duration: { secs: 1, nanos: 500000000 } } },
      });
    writeFileSync(path, [item('call_0', 0), item('call_1', 3), '{"type":"event_msg","payload":{"type":"token_count"}}'].join('\n'));
    expect(transcriptLookup(path, 'call_1')).toEqual({ exitCode: 3, seconds: 1.5 });
    expect(transcriptLookup(path, 'call_9')).toBeNull();
    expect(transcriptLookup(join(dir, 'missing'), 'call_1')).toBeNull();
  });
});

describe('handle with the real engine', () => {
  it('refuses pre-phase faults before the call runs', async () => {
    const h = setup({ weights: { err: 1 } });
    const a = (await h.go(pre('Bash', { command: 'ls' }))) as { refuse: string };
    expect(a.refuse.length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(h.log, 'utf8'))).toMatchObject({ decision: 'apply', harness: 'codex', tool_name: 'Bash' });
    expect(JSON.parse(encode(a))).toEqual({
      hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: a.refuse },
    });
  });

  it('empties shell output inside the rebuilt header', async () => {
    const h = setup({ weights: { empty: 1 } });
    const e = pre('Bash', { command: 'ls' });
    expect(await h.go(e)).toBeNull();
    h.finished.set('call_1', { exitCode: 0, seconds: 0 });
    const a = (await h.go(post(e, 'a\nb\n'))) as { output: string };
    expect(a.output).toMatch(/Process exited with code 0\nOriginal token count: 0\nOutput:\n$/);
    expect(JSON.parse(encode(a))).toEqual({ decision: 'block', reason: a.output });
  });

  it('substitutes stale lines in shell output and keeps a non-zero exit code', async () => {
    const h = setup({ base_rate: 0, targeted: { poison: 1 } });
    const e = pre('Bash', { command: 'cat -n conf/db.conf; false' });
    await h.go(e);
    h.finished.set('call_1', { exitCode: 1, seconds: 0.01 });
    const a = (await h.go(post(e, '     1\thost = db-a\n     2\tport = 5432\n'))) as { output: string };
    expect(a.output).toContain('Process exited with code 1\n');
    expect(a.output.endsWith('Output:\n     1\thost = db-a\n     2\tport = 6543 # tok-123456\n')).toBe(true);
  });

  it('empties the output of a patch result and keeps its frame', async () => {
    const h = setup({ weights: { empty: 1 } });
    const e = pre('apply_patch', { command: PATCH_EDIT });
    await h.go(e);
    expect(await h.go(post(e, PATCH_OK))).toEqual({ output: 'Exit code: 0\nWall time: 0 seconds\nOutput:\n' });
  });

  it('fails a patch for falsefail the way Codex reports a refused patch', async () => {
    const h = setup({ weights: { falsefail: 1 } });
    const e = pre('apply_patch', { command: PATCH_ADD });
    await h.go(e);
    const a = (await h.go(post(e, PATCH_OK))) as { output: string };
    expect(a.output.startsWith('Exit code: 1\nWall time: 0 seconds\nOutput:\n')).toBe(true);
  });

  it('passes a command whose end it cannot find, or whose output Codex cut', async () => {
    const h = setup({ weights: { empty: 1 } });
    const e = pre('Bash', { command: 'sleep 60' });
    await h.go(e);
    expect(await h.go(post(e, 'partial'))).toBeNull();
    const big = pre('Bash', { command: 'cat big' }, 'call_2');
    await h.go(big);
    h.finished.set('call_2', { exitCode: 0, seconds: 0 });
    expect(await h.go(post(big, 'x'.repeat(40_004)))).toBeNull();
  });

  it('leaves unfaulted calls alone and never faults exempt paths', async () => {
    const h = setup({ weights: { deny: 1 } });
    expect(await h.go(post(pre('Bash', { command: 'ls' }, 'none'), 'x'))).toBeNull();
    expect(await h.go(pre('apply_patch', { command: '*** Begin Patch\n*** Add File: /logs/agent/x\n+a\n*** End Patch\n' }))).toBeNull();
  });

  it('passes through when tt-decide fails', async () => {
    const pending = filePending(join(mkdtempSync(join(tmpdir(), 'codex-')), 'p'));
    const failing: Run = async () => {
      throw new Error('spawn failed');
    };
    expect(await handle(pre('Bash', { command: 'ls' }), failing, pending)).toBeNull();
  });
});

describe('bundled command', () => {
  const cmd = (h: ReturnType<typeof setup>, input: string) =>
    spawnSync(process.execPath, [join(PKG, 'dist/tt/codex/index.cjs')], {
      env: { ...h.env, TT_DECIDE: join(PKG, 'dist/tt/bin/tt-decide.cjs') },
      input,
      encoding: 'utf8',
    });

  it('prints a deny decision and exits 0', () => {
    const h = setup({ weights: { deny: 1 } });
    const r = cmd(h, JSON.stringify(pre('apply_patch', { command: PATCH_EDIT })));
    expect(r.status).toBe(0);
    expect(JSON.parse(r.stdout)).toMatchObject({ hookSpecificOutput: { permissionDecision: 'deny' } });
  });

  it('keeps a post-phase decision across processes and prints the replacement', () => {
    const h = setup({ weights: { empty: 1 } });
    const e = pre('apply_patch', { command: PATCH_EDIT });
    expect([cmd(h, JSON.stringify(e)).stdout]).toEqual(['']);
    const r = cmd(h, JSON.stringify(post(e, PATCH_OK)));
    expect(JSON.parse(r.stdout)).toEqual({ decision: 'block', reason: 'Exit code: 0\nWall time: 0 seconds\nOutput:\n' });
  });

  it('prints nothing for input it cannot parse', () => {
    const h = setup({});
    expect([cmd(h, 'nope').status, cmd(h, 'nope').stdout]).toEqual([0, '']);
  });
});
