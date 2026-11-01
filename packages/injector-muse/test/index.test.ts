import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import { capabilityOf, encode, filePending, handle, pathsOf, textView, tokenCount, type CallEvent, type Run } from '../src/index.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');
const PKG = resolve(import.meta.dirname, '..');

beforeAll(() => {
  // build.mjs deletes dist first, and the cli lint test reads dist while the
  // workspace tests run in parallel, so only build when `pnpm build` has not.
  const steps: [string, string][] = [[ENGINE, 'scripts/bundle.mjs']];
  if (!existsSync(join(PKG, 'dist/tt/muse/index.cjs'))) steps.push([PKG, 'scripts/build.mjs']);
  for (const [cwd, script] of steps) {
    const r = spawnSync(process.execPath, [script], { cwd, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
  }
});

const ORIGINAL = 'host = db-a\nport = 5432\nregion = west\n';
const VARIANT = 'host = db-a\nport = 6543 # tok-123456\nregion = west\n';

function setup(profile: { weights?: Record<string, number>; targeted?: Record<string, number>; base_rate?: number }) {
  const dir = mkdtempSync(join(tmpdir(), 'muse-'));
  const cfg = resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 's',
    task_id: 'probe',
    attempt: 0,
    harness: 'muse',
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
      poison: [
        { tool: 'shell', source: '/app/conf/db.conf', variant: 'variants/db.conf', token: 'tok-123456' },
        { tool: 'fs.read', match: { path: 'conf/db.conf' }, variant: 'variants/db.conf', token: 'tok-123456' },
      ],
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
  return { dir, env, log: env.TT_LOG, go: (e: CallEvent) => handle(e, run, pending) };
}

const call = (tool: string, input: Record<string, unknown>, id = 'c1'): CallEvent => ({
  hook_event_name: 'PreToolUse',
  session_id: 's1',
  cwd: '/app',
  tool_name: tool,
  tool_input: input,
  tool_use_id: id,
});
const post = (e: CallEvent, response: unknown): CallEvent => ({ ...e, hook_event_name: 'PostToolUse', tool_response: response });
// Same shape as the bash results in docs/verification/V-29/2026-10-31-model.
const shellOut = (out: string, exit = 0) =>
  JSON.stringify(
    {
      chunk_id: 'exec-1-1',
      command: 'ls',
      exit_code: exit,
      terminal_status: exit === 0 ? 'completed' : 'failed',
      output: out,
      original_output_bytes: Buffer.byteLength(out),
      original_output_tokens: tokenCount(out),
      truncated: false,
    },
    null,
    2,
  );
const readOut = (path: string, lines: string[], first = 1) =>
  `Read text file \`${path}\`.\n` + lines.map((l, i) => `${first + i}|${l}`).join('\n');

describe('mapping', () => {
  it('maps Muse tools and resolves relative paths against the workspace', () => {
    expect(capabilityOf('read_file')).toBe('fs.read');
    expect(capabilityOf('write_file')).toBe('fs.write');
    expect(capabilityOf('edit_file')).toBe('fs.edit');
    expect(capabilityOf('search')).toBe('fs.search');
    expect(capabilityOf('bash')).toBe('shell');
    expect(capabilityOf('bash_input')).toBeNull();
    expect(capabilityOf('submit_reminder_decision')).toBeNull();
    expect(capabilityOf('mcp__tickets__get_ticket')).toBeNull();
    expect(pathsOf({ path: 'src/a.ts' }, '/app')).toEqual(['/app/src/a.ts']);
    expect(pathsOf({ path: '/etc/x' }, '/app')).toEqual(['/etc/x']);
    expect(pathsOf({ command: 'ls' }, '/app')).toEqual([]);
  });

  it('counts tokens as Muse does', () => {
    expect(tokenCount('x'.repeat(236))).toBe(59);
    expect(tokenCount('x'.repeat(49))).toBe(13);
  });
});

describe('text views', () => {
  it('strips and renumbers read_file lines', () => {
    const out = readOut('a.txt', ['nine', 'ten', 'eleven'], 9);
    const v = textView('read_file', out)!;
    expect(v.text).toBe('nine\nten\neleven');
    expect(v.with(v.text)).toBe(out);
    expect(v.with('nine')).toBe('Read text file `a.txt`.\n9|nine');
    expect(v.with('')).toBe('Read text file `a.txt`.\n');
    expect(textView('read_file', 'Read text file `e.txt`.\n')).toBeNull();
  });

  it('replaces bash output inside the result object and recounts its size', () => {
    const v = textView('bash', shellOut('a\nb\n'))!;
    expect(v.text).toBe('a\nb\n');
    expect(v.with(v.text)).toBe(shellOut('a\nb\n'));
    expect(v.with('a\n')).toBe(shellOut('a\n'));
    expect(textView('bash', 'not json')).toBeNull();
    expect(textView('bash', JSON.stringify({ output: 'x', truncated: true }))).toBeNull();
  });

  it('has no view for write and edit results', () => {
    expect(textView('write_file', 'wrote 6 bytes to /app/a.txt')).toBeNull();
  });
});

describe('handle with the real engine', () => {
  it('refuses pre-phase faults before the call runs', async () => {
    const h = setup({ weights: { err: 1 } });
    const a = (await h.go(call('bash', { command: 'ls' }))) as { refuse: string };
    expect(a.refuse.length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(h.log, 'utf8'))).toMatchObject({ decision: 'apply', harness: 'muse', tool_name: 'bash' });
  });

  it('truncates a read_file result after the call ran', async () => {
    const h = setup({ weights: { trunc: 1 } });
    const e = call('read_file', { path: 'a.txt' });
    expect(await h.go(e)).toBeNull();
    const lines = Array.from({ length: 10 }, (_, i) => `line ${i}`);
    const a = (await h.go(post(e, readOut('a.txt', lines)))) as { output: string };
    expect(textView('read_file', a.output)!.text).toBe(Array.from(lines.join('\n')).slice(0, Math.floor(lines.join('\n').length * 0.3)).join(''));
  });

  it('empties bash output', async () => {
    const h = setup({ weights: { empty: 1 } });
    const e = call('bash', { command: 'ls' });
    await h.go(e);
    const a = (await h.go(post(e, shellOut('a\nb\n')))) as { output: string };
    expect(a.output).toBe(shellOut(''));
  });

  it('replaces a write result with the failure text for falsefail', async () => {
    const h = setup({ weights: { falsefail: 1 } });
    const e = call('write_file', { path: 'a.txt', content: 'x' });
    await h.go(e);
    const a = (await h.go(post(e, { filePath: '/app/a.txt', structuredPatch: [] }))) as { output: string };
    expect(a.output.length).toBeGreaterThan(0);
    expect(JSON.parse(encode(a))).toEqual({ decision: 'block', reason: a.output });
  });

  it('substitutes stale lines in bash output', async () => {
    const h = setup({ base_rate: 0, targeted: { poison: 1 } });
    const e = call('bash', { command: 'cat -n conf/db.conf' });
    await h.go(e);
    const a = (await h.go(post(e, shellOut('     1\thost = db-a\n     2\tport = 5432\n')))) as { output: string };
    expect(JSON.parse(a.output).output).toBe('     1\thost = db-a\n     2\tport = 6543 # tok-123456\n');
  });

  it('shows the declared variant for a matching read_file call', async () => {
    const h = setup({ base_rate: 0, targeted: { poison: 1 } });
    const e = call('read_file', { path: 'conf/db.conf' });
    await h.go(e);
    const a = (await h.go(post(e, readOut('conf/db.conf', ORIGINAL.trimEnd().split('\n'))))) as { output: string };
    expect(a.output).toBe(readOut('conf/db.conf', ['host = db-a', 'port = 6543 # tok-123456', 'region = west']));
  });

  it('leaves failed calls and unfaulted calls alone', async () => {
    const h = setup({ weights: { trunc: 1 } });
    expect(await h.go(post(call('bash', { command: 'ls' }, 'none'), shellOut('x')))).toBeNull();
    const e = call('bash', { command: 'cat missing' }, 'c2');
    await h.go(e);
    expect(await h.go({ ...e, hook_event_name: 'PostToolUseFailure', error: shellOut('cat: missing: No such file\n', 1) })).toBeNull();
    const records = readFileSync(h.log, 'utf8').trim().split('\n').map((l) => JSON.parse(l) as Record<string, unknown>);
    const applied = records.filter((r) => r.decision === 'apply' && r.tool_name === 'bash').at(-1)!;
    expect(records.at(-1)).toMatchObject({
      decision: 'undelivered',
      seq: null,
      of_seq: applied.seq,
      type: 'trunc',
      tool_name: 'bash',
      capability: 'shell',
      reason: 'failed-call',
    });
  });

  it('never faults exempt paths', async () => {
    const h = setup({ weights: { deny: 1 } });
    expect(await h.go(call('read_file', { path: '/logs/agent/x' }))).toBeNull();
  });

  it('passes through when tt-decide fails', async () => {
    const pending = filePending(join(mkdtempSync(join(tmpdir(), 'muse-')), 'p'));
    const failing: Run = async () => {
      throw new Error('down');
    };
    expect(await handle(call('bash', { command: 'ls' }), failing, pending)).toBeNull();
  });
});

describe('command', () => {
  it('runs as Muse runs it: event on stdin, refusal on stderr with exit 2', () => {
    const h = setup({ weights: { deny: 1 } });
    const r = spawnSync(process.execPath, [join(PKG, 'dist/tt/muse/index.cjs')], {
      env: { ...h.env, TT_DECIDE: BIN },
      input: JSON.stringify(call('bash', { command: 'ls' })),
      encoding: 'utf8',
    });
    expect(r.status).toBe(2);
    expect(r.stderr.length).toBeGreaterThan(0);
    expect(existsSync(h.log)).toBe(true);
  });
});
