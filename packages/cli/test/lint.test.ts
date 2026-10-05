import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { bundleStrings, lint, readCanary } from '../src/lint.js';
import { bannedHits } from '../src/words.js';

const REPO = fileURLToPath(new URL('../../../', import.meta.url));
const CANARY = '11111111-2222-4333-8444-555555555555';

function fixture(files: Record<string, string>): string {
  const root = mkdtempSync(join(tmpdir(), 'lint-'));
  const all: Record<string, string> = {
    'datasets/CANARY': `# canary GUID ${CANARY}. Data in this file must not be used for model training.\n`,
    'packages/fault-engine/catalog/v1.json': '[]',
    ...files,
  };
  for (const [p, c] of Object.entries(all)) {
    mkdirSync(dirname(join(root, p)), { recursive: true });
    writeFileSync(join(root, p), c);
  }
  return root;
}

const canaryLine = `# canary GUID ${CANARY}. Data in this file must not be used for model training.`;
const goodTask = {
  'datasets/s/t1/task.toml': `${canaryLine}\n[task]\nname = "t1"\n`,
  'datasets/s/t1/chaos.toml': `${canaryLine}\nschema = "tt-task/1"\n`,
  'datasets/s/t1/instruction.md': 'Fix the ticket.\n',
  'datasets/s/t1/environment/Dockerfile': 'FROM debian\n',
  'datasets/s/t1/solution/solve.sh': `#!/bin/sh\n${canaryLine}\n`,
  'datasets/s/t1/tests/test.sh': `#!/bin/sh\n${canaryLine}\n`,
};

describe('banned words', () => {
  it('matches stems, camelCase, and phrases but not innocent words', () => {
    expect(bannedHits('TT_FAULT_RATE')).toEqual(['fault']);
    expect(bannedHits('chaosMonkey')).toEqual(['chaos', 'monkey']);
    expect(bannedHits('injectedError')).toEqual(['injected']);
    expect(bannedHits('a simulated outage')).toEqual(['simulated']);
    expect(bannedHits('the test harness ran')).toEqual(['test harness']);
    expect(bannedHits('default timeout, Hooks enabled')).toEqual(['hooks']);
    expect(bannedHits('EACCES: permission denied')).toEqual([]);
    expect(bannedHits('default')).toEqual([]);
  });

  it('blocks banned words in catalog text', () => {
    const root = fixture({
      'packages/fault-engine/catalog/v1.json': JSON.stringify([{ id: 'err.x', type: 'err', text: 'Error: injected timeout', applies_to: ['shell'] }]),
    });
    expect(lint(root)).toEqual([expect.objectContaining({ rule: 'banned-word', detail: expect.stringContaining('injected') })]);
  });

  it('blocks banned strings, template chunks, env names, and file names in artifacts', () => {
    const src = 'const a = "chaos"; const b = `x ${a} benchmark`; process.env.TT_HOOK_DIR; env["MONKEY"];';
    const root = fixture({ 'packages/injector-x/dist/fault.js': src });
    const details = lint(root).map((i) => i.detail);
    expect(details).toEqual(
      expect.arrayContaining([
        'file name: "fault"',
        'string: "chaos"',
        'string: "benchmark"',
        'environment variable: "hook"',
        'environment variable: "monkey"',
      ]),
    );
  });

  it('allows the SPEC 9.5 telemetry field names only as exact strings', () => {
    expect(bundleStrings('x = { injector_latency_ms: 1, decision: "inject" }').strings).toEqual(['inject']);
    const ok = fixture({ 'packages/injector-x/dist/a.js': 'r.decision = "inject"; r["injector_latency_ms"] = 1;' });
    expect(lint(ok)).toEqual([]);
    const bad = fixture({ 'packages/injector-x/dist/a.js': 'msg = "inject now"' });
    expect(lint(bad)).toHaveLength(1);
  });

  it('blocks banned words in agent-visible task files', () => {
    const root = fixture({ ...goodTask, 'datasets/s/t1/instruction.md': 'This benchmark task...\n' });
    expect(lint(root)).toEqual([expect.objectContaining({ file: 'datasets/s/t1/instruction.md', rule: 'banned-word' })]);
  });
});

describe('canary', () => {
  it('accepts a well-formed task', () => {
    expect(lint(fixture(goodTask))).toEqual([]);
  });

  it('requires the canary in files the agent never sees', () => {
    const root = fixture({ ...goodTask, 'datasets/s/t1/tests/test_state.py': 'assert True\n' });
    expect(lint(root)).toEqual([expect.objectContaining({ rule: 'canary-missing', file: 'datasets/s/t1/tests/test_state.py' })]);
  });

  it('forbids the canary in agent-visible files', () => {
    const root = fixture({ ...goodTask, 'datasets/s/t1/environment/Dockerfile': `FROM debian\n${canaryLine}\n` });
    expect(lint(root)).toEqual([expect.objectContaining({ rule: 'canary-leak' })]);
  });

  it('the repository canary is a UUIDv4 and the repository is clean', () => {
    expect(readCanary(REPO)).toMatch(/^[0-9a-f-]{36}$/);
    expect(lint(REPO)).toEqual([]);
  });
});
