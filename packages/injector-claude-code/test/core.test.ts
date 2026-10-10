import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { resolveEngineConfig, type EngineConfigInput } from '@cmca/fault-engine';
import { beforeAll, describe, expect, it } from 'vitest';
import { capabilityOf, handle, pathsOf, textView, type CallEvent, type CallResult, type Run } from '../plugin/hooks/core.js';

const ENGINE = resolve(import.meta.dirname, '../../fault-engine');
const BIN = join(ENGINE, 'dist/bin/tt-decide.cjs');

beforeAll(() => {
  const r = spawnSync(process.execPath, ['scripts/bundle.mjs'], { cwd: ENGINE, encoding: 'utf8' });
  if (r.status !== 0) throw new Error(r.stderr);
});

function engineConfig(weights: Record<string, number>, overrides: Record<string, unknown> = {}) {
  return resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 'test-seed',
    task_id: 'probe',
    attempt: 0,
    harness: 'claude-code',
    layer: 'native',
    profile: {
      schema: 'tt-profile/1',
      name: 'probe',
      base_rate: 1,
      max_faults_per_trial: 100,
      persistence: { transient: 1 },
      weights,
    },
    parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'],
    catalog_version: 'v1',
    task: { schema: 'tt-task/1' },
    ...overrides,
  } as EngineConfigInput);
}

/** Runs the real tt-decide bundle in place of `$.process.run`. */
function realRun(cfg: unknown): { run: Run; log: string } {
  const dir = mkdtempSync(join(tmpdir(), 'cc-'));
  writeFileSync(join(dir, 'config.json'), JSON.stringify(cfg));
  const env = { ...process.env, TT_CONFIG: join(dir, 'config.json'), TT_STATE: join(dir, 'state'), TT_LOG: join(dir, 'events.jsonl') };
  const run: Run = async (argv, init) => {
    const r = spawnSync(process.execPath, [BIN, ...argv.slice(2)], { env, input: init.stdin, encoding: 'utf8' });
    return { exitCode: r.status ?? 1, stdout: r.stdout };
  };
  return { run, log: env.TT_LOG };
}

const bash = (command: string): CallEvent => ({ tool: 'Bash', tool_use_id: 't1', command });
const bashResult = (stdout: string): CallResult => ({ result: { stdout, stderr: '', interrupted: false } });

function nextSpy(res: CallResult) {
  const calls: CallEvent[] = [];
  return { calls, next: async (e: CallEvent) => (calls.push(e), res) };
}

describe('tool mapping', () => {
  it('maps built-in and MCP tools to capability classes', () => {
    expect(capabilityOf('Read')).toBe('fs.read');
    expect(capabilityOf('Glob')).toBe('fs.search');
    expect(capabilityOf('Bash')).toBe('shell');
    expect(capabilityOf('mcp__issues__create_issue')).toBe('mcp.issues.create_issue');
    expect(capabilityOf('TodoWrite')).toBeNull();
    expect(capabilityOf('Task')).toBeNull();
  });

  it('extracts absolute paths for exemptions', () => {
    expect(pathsOf('Read', { file_path: '/logs/x' })).toEqual(['/logs/x']);
    expect(pathsOf('Grep', { pattern: 'a', path: '/app' })).toEqual(['/app']);
    expect(pathsOf('Bash', { command: 'cat /logs/x' })).toEqual([]);
  });

  it('keeps result shapes valid when replacing text', () => {
    const read = { type: 'text', file: { filePath: '/a', content: 'a\nb\nc', numLines: 3, startLine: 1, totalLines: 3 } };
    expect(textView('Read', read)!.with('a')).toEqual({
      ...read,
      file: { ...read.file, content: 'a', numLines: 1, totalLines: 1 },
    });
    const empty = textView('Read', { type: 'text', file: { ...read.file, totalLines: 41 } })!.with('') as typeof read;
    expect(empty.file).toMatchObject({ numLines: 0, totalLines: 0 });
    const tail = { type: 'text', file: { ...read.file, startLine: 10, totalLines: 41 } };
    expect((textView('Read', tail)!.with('x\ny') as typeof read).file.totalLines).toBe(11);
    const glob = { durationMs: 1, numFiles: 2, filenames: ['/a', '/b'], truncated: false };
    expect(textView('Glob', glob)!.with('')).toEqual({ ...glob, filenames: [], numFiles: 0 });
    expect(textView('Read', { type: 'image', file: {} })).toBeNull();
  });
});

describe('handle with the real engine', () => {
  it('passes unmapped tools straight through', async () => {
    const { run } = realRun(engineConfig({ deny: 1 }));
    const spy = nextSpy({ result: 'ok' });
    const e = { tool: 'TodoWrite', tool_use_id: 't', todos: [] };
    expect(await handle(e, spy.next, run)).toEqual({ result: 'ok' });
    expect(spy.calls).toEqual([e]);
  });

  it('refuses a pre-phase fault without running the tool', async () => {
    const { run, log } = realRun(engineConfig({ err: 1 }));
    const spy = nextSpy(bashResult('x'));
    const out = await handle(bash('ls'), spy.next, run);
    expect(spy.calls).toHaveLength(0);
    expect('deny' in out && (out.deny ?? '').length).toBeGreaterThan(0);
    expect(JSON.parse(readFileSync(log, 'utf8').trim())).toMatchObject({ decision: 'apply', type: 'err', capability: 'shell' });
  });

  it('truncates the output of a call that ran', async () => {
    const { run } = realRun(engineConfig({ trunc: 1 }));
    const spy = nextSpy(bashResult('0123456789'));
    const out = await handle(bash('ls'), spy.next, run);
    expect(spy.calls).toHaveLength(1);
    expect(out).toEqual(bashResult('012'));
  });

  it('reports an error for a call that ran under falsefail', async () => {
    const { run } = realRun(engineConfig({ falsefail: 1 }));
    const spy = nextSpy({ result: { type: 'create', filePath: '/app/a', content: 'x' } });
    const out = await handle({ tool: 'Write', tool_use_id: 't', file_path: '/app/a', content: 'x' }, spy.next, run);
    expect(spy.calls).toHaveLength(1);
    expect('deny' in out && out.deny).toMatch(/ECONNRESET/);
  });

  it('never faults exempt paths', async () => {
    const { run, log } = realRun(engineConfig({ deny: 1 }));
    const spy = nextSpy({ result: 'r' });
    await handle({ tool: 'Read', tool_use_id: 't', file_path: '/logs/agent/x' }, spy.next, run);
    expect(spy.calls).toHaveLength(1);
    expect(JSON.parse(readFileSync(log, 'utf8').trim())).toMatchObject({ decision: 'pass', exempt_reason: 'exempt_path' });
  });

  it('records the subagent id', async () => {
    const { run, log } = realRun(engineConfig({ deny: 1 }, { profile: { schema: 'tt-profile/1', name: 'clean', base_rate: 0, max_faults_per_trial: 0 } }));
    await handle({ ...bash('ls'), agentId: 'a-1' }, nextSpy(bashResult('')).next, run);
    expect(JSON.parse(readFileSync(log, 'utf8').trim())).toMatchObject({ agent_id: 'a-1', decision: 'pass' });
  });

  it('runs the tool when tt-decide fails', async () => {
    const failing: Run = async () => ({ exitCode: 1, stdout: '' });
    const spy = nextSpy(bashResult('x'));
    expect(await handle(bash('ls'), spy.next, failing)).toEqual(bashResult('x'));
  });
});
