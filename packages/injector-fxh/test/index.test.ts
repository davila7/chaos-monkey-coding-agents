import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import { capabilityOf, encode, filePending, handle, pathsOf, textView, type CallEvent, type Run } from '../src/index.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');
const PKG = resolve(import.meta.dirname, '..');

beforeAll(() => {
  for (const [cwd, script] of [
    [ENGINE, 'scripts/bundle.mjs'],
    [PKG, 'scripts/build.mjs'],
  ] as const) {
    const r = spawnSync(process.execPath, [script], { cwd, encoding: 'utf8' });
    if (r.status !== 0) throw new Error(r.stderr);
  }
});

const ORIGINAL = 'host = db-a\nport = 5432\nregion = west\n';
const VARIANT = 'host = db-a\nport = 6543 # tok-123456\nregion = west\n';

function setup(profile: { weights?: Record<string, number>; targeted?: Record<string, number>; base_rate?: number }) {
  const dir = mkdtempSync(join(tmpdir(), 'fxh-'));
  const cfg = resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 's',
    task_id: 'probe',
    attempt: 0,
    harness: 'fxh',
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
  cwd: '/app',
  tool_name: tool,
  tool_input: input,
  tool_use_id: id,
});
const shellOut = (out: string, exit = 0) =>
  JSON.stringify({ session_id: null, state: 'completed', full_output_handle: 'fx-command-replay-1.bin', exit_code: exit, output_delta: out });
const readOut = (path: string, lines: string[], first = 1, note = '') => {
  const width = String(first + lines.length - 1).length;
  const body = lines.map((l, i) => `${String(first + i).padEnd(width)}\t${l}\n`).join('');
  return `<path>${path}</path>\n<content>\n${body}${note}</content>`;
};

describe('mapping', () => {
  it('maps fx tools and resolves relative paths against the workspace', () => {
    expect(capabilityOf('read_file', {})).toBe('fs.read');
    expect(capabilityOf('glob_files', {})).toBe('fs.search');
    expect(capabilityOf('shell', { action: 'run', command: 'ls' })).toBe('shell');
    expect(capabilityOf('shell', { action: 'interact', session_id: 's' })).toBeNull();
    expect(capabilityOf('mcp_tickets_list_open', {})).toBeNull();
    expect(capabilityOf('web_fetch', {})).toBeNull();
    expect(pathsOf({ path: 'src/a.ts' }, '/app')).toEqual(['/app/src/a.ts']);
    expect(pathsOf({ path: '/etc/x' }, '/app')).toEqual(['/etc/x']);
    expect(pathsOf({ command: 'ls' }, '/app')).toEqual([]);
  });
});

describe('text views', () => {
  it('strips and renumbers read_file lines, keeping the note only at the same length', () => {
    const out = readOut('a.txt', ['nine', 'ten', 'eleven'], 9, '... [showing 3 of 20 lines; use start_line/line_count to read more.]\n');
    expect(out).toContain('9 \tnine\n10\tten');
    const v = textView('read_file', out)!;
    expect(v.text).toBe('nine\nten\neleven');
    expect(v.with(v.text)).toBe(out);
    expect(v.with('nine')).toBe('<path>a.txt</path>\n<content>\n9\tnine\n</content>');
    expect(v.with('')).toBe('<path>a.txt</path>\n<content>\n</content>');
  });

  it('has no read_file view for binary, image or empty results', () => {
    expect(textView('read_file', '<path>a.bin</path>\n<content>binary or non-utf8 file omitted (9 bytes)</content>')).toBeNull();
    expect(textView('read_file', '<path>e.txt</path>\n<content>\n</content>')).toBeNull();
  });

  it('replaces shell output and drops the handle to the original', () => {
    const v = textView('shell', shellOut('a\nb\n'))!;
    expect(v.text).toBe('a\nb\n');
    expect(JSON.parse(v.with('a\n'))).toEqual({ ...JSON.parse(shellOut('a\n')), full_output_handle: null });
    expect(textView('shell', 'not json')).toBeNull();
  });

  it('writes grep matches with a grep -n prefix and back', () => {
    const out = '[grep] 2 matches for port\n - conf/db.conf:2: port = 5432\n - b.txt:7: port\n';
    const v = textView('grep_files', out)!;
    expect(v.text).toBe('[grep] 2 matches for port\nconf/db.conf:2:port = 5432\nb.txt:7:port\n');
    expect(v.with(v.text)).toBe(out);
    expect(v.with(v.text.replace('5432', '6543'))).toBe(out.replace('5432', '6543'));
  });

  it('keeps the match lead when a cut falls inside the prefix', () => {
    const v = textView('grep_files', '[grep] 1 matches for x\n - probe/docs/a.txt:3: x\n')!;
    expect(v.with('[grep] 1 matches for x\nprobe/d')).toBe('[grep] 1 matches for x\n - probe/d');
  });
});

describe('handle with the real engine', () => {
  it('refuses pre-phase faults before the call runs', async () => {
    const h = setup({ weights: { err: 1 } });
    const a = (await h.go(call('shell', { action: 'run', command: 'ls' }))) as { refuse: string };
    expect(a.refuse.length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(h.log, 'utf8'))).toMatchObject({ decision: 'apply', harness: 'fxh', tool_name: 'shell' });
  });

  it('truncates a read_file result after the call ran', async () => {
    const h = setup({ weights: { trunc: 1 } });
    const e = call('read_file', { path: 'a.txt' });
    expect(await h.go(e)).toBeNull();
    const lines = Array.from({ length: 10 }, (_, i) => `line ${i}`);
    const a = (await h.go({ ...e, tool_response: readOut('a.txt', lines) })) as { output: string; failed: boolean };
    expect(a.failed).toBe(false);
    expect(textView('read_file', a.output)!.text).toBe(Array.from(lines.join('\n')).slice(0, Math.floor(lines.join('\n').length * 0.3)).join(''));
  });

  it('empties shell output', async () => {
    const h = setup({ weights: { empty: 1 } });
    const e = call('shell', { action: 'run', command: 'ls' });
    await h.go(e);
    const a = (await h.go({ ...e, tool_response: shellOut('a\nb\n') })) as { output: string };
    expect(JSON.parse(a.output)).toMatchObject({ output_delta: '', full_output_handle: null, exit_code: 0 });
  });

  it('turns a falsefail result into a failure', async () => {
    const h = setup({ weights: { falsefail: 1 } });
    const e = call('write_file', { path: 'a.txt', content: 'x' });
    await h.go(e);
    const a = (await h.go({ ...e, tool_response: 'Wrote a.txt' })) as { output: string; failed: boolean };
    expect(a.failed).toBe(true);
    expect(encode(a)).toContain('"updatedToolOutputIsError":true');
  });

  it('substitutes stale lines in shell output, also when the command exited non-zero', async () => {
    const h = setup({ base_rate: 0, targeted: { poison: 1 } });
    const e = call('shell', { action: 'run', command: 'cat -n conf/db.conf; false' });
    await h.go(e);
    const out = shellOut('     1\thost = db-a\n     2\tport = 5432\n', 1);
    const a = (await h.go({ ...e, tool_response: out, tool_failed: true })) as { output: string; failed: boolean };
    expect(a.failed).toBe(false);
    expect(JSON.parse(a.output).output_delta).toBe('     1\thost = db-a\n     2\tport = 6543 # tok-123456\n');
  });

  it('shows the declared variant for a matching read_file call', async () => {
    const h = setup({ base_rate: 0, targeted: { poison: 1 } });
    const e = call('read_file', { path: 'conf/db.conf' });
    await h.go(e);
    const a = (await h.go({ ...e, tool_response: readOut('conf/db.conf', ORIGINAL.trimEnd().split('\n')) })) as { output: string };
    expect(a.output).toBe(readOut('conf/db.conf', ['host = db-a', 'port = 6543 # tok-123456', 'region = west']));
  });

  it('leaves unfaulted calls and calls that failed by themselves alone', async () => {
    const h = setup({ weights: { trunc: 1 } });
    expect(await h.go({ ...call('shell', { command: 'ls' }, 'none'), tool_response: shellOut('x') })).toBeNull();
    const e = call('read_file', { path: 'missing.txt' }, 'c2');
    await h.go(e);
    const failure = JSON.stringify({ error: { type: 'tool_execution_failed', tool_name: 'read_file', message: 'not found' } });
    expect(await h.go({ ...e, tool_response: failure, tool_failed: true })).toBeNull();
  });

  it('never faults exempt paths', async () => {
    const h = setup({ weights: { deny: 1 } });
    expect(await h.go(call('read_file', { path: '/logs/agent/x' }))).toBeNull();
  });

  it('passes through when tt-decide fails', async () => {
    const pending = filePending(join(mkdtempSync(join(tmpdir(), 'fxh-')), 'p'));
    const failing: Run = async () => {
      throw new Error('spawn failed');
    };
    expect(await handle(call('shell', { command: 'ls' }), failing, pending)).toBeNull();
  });
});

describe('bundled command', () => {
  const cmd = (h: ReturnType<typeof setup>, e: CallEvent) =>
    spawnSync(process.execPath, [join(PKG, 'dist/tt/fxh/index.cjs')], {
      env: { ...h.env, TT_DECIDE: join(PKG, 'dist/tt/bin/tt-decide.cjs') },
      input: JSON.stringify(e),
      encoding: 'utf8',
    });

  it('refuses with exit code 2 and the message on stderr', () => {
    const h = setup({ weights: { deny: 1 } });
    const r = cmd(h, call('edit_file', { path: 'a.txt', old_string: 'a', new_string: 'b' }));
    expect(r.status).toBe(2);
    expect(r.stdout).toBe('');
    expect(r.stderr.length).toBeGreaterThan(0);
  });

  it('keeps a post-phase decision across processes and prints the replacement', () => {
    const h = setup({ weights: { empty: 1 } });
    const e = call('grep_files', { pattern: 'x' });
    const pre = cmd(h, e);
    expect([pre.status, pre.stdout, pre.stderr]).toEqual([0, '', '']);
    const post = cmd(h, { ...e, tool_response: '[grep] 1 matches for x\n - a:1: x\n', tool_failed: false });
    expect(post.status).toBe(0);
    expect(JSON.parse(post.stdout)).toEqual({ hookSpecificOutput: { updatedToolOutput: '' } });
  });

  it('prints nothing for input it cannot parse', () => {
    const h = setup({});
    const r = spawnSync(process.execPath, [join(PKG, 'dist/tt/fxh/index.cjs')], { env: h.env, input: 'nope', encoding: 'utf8' });
    expect([r.status, r.stdout]).toEqual([0, '']);
  });
});
