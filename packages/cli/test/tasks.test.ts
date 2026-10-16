import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { bumpIssues, COMPLETION_CONTRACT, semverGreater, taskFileIssues, taskVersion } from '../src/tasks.js';

function write(root: string, files: Record<string, string>) {
  for (const [p, c] of Object.entries(files)) {
    mkdirSync(dirname(join(root, p)), { recursive: true });
    writeFileSync(join(root, p), c);
  }
}

const toml = (version: string | null) => `# canary\nschema_version = "1.4"\n\n[task]\nname = "cmca/t"\n${version ? `version = "${version}"\n` : ''}\n[agent]\ntimeout_sec = 60\n`;

describe('task files', () => {
  it('reads the version from the [task] table only', () => {
    expect(taskVersion(toml('1.2.3'))).toBe('1.2.3');
    expect(taskVersion('[agent]\nversion = "9.9.9"\n')).toBeNull();
  });

  it('compares versions numerically', () => {
    expect(semverGreater('1.10.0', '1.9.9')).toBe(true);
    expect(semverGreater('1.0.0', '1.0.0')).toBe(false);
    expect(semverGreater('2.0', '1.0.0')).toBe(false);
  });

  it('flags a missing version, a bad chaos schema and a missing completion contract', () => {
    const dir = mkdtempSync(join(tmpdir(), 'task-'));
    write(dir, { 'task.toml': toml(null), 'chaos.toml': 'schema = "x"\n', 'instruction.md': 'Do it.\n' });
    expect(taskFileIssues(dir, true).map((i) => i.rule)).toEqual(['task-version', 'chaos-schema', 'instruction-contract']);
    expect(taskFileIssues(dir, false).map((i) => i.rule)).toEqual(['task-version', 'chaos-schema']);
    write(dir, { 'task.toml': toml('1.0.0'), 'chaos.toml': 'schema = "tt-task/1"\n', 'instruction.md': `Do it.\n\n${COMPLETION_CONTRACT}\n` });
    expect(taskFileIssues(dir, true)).toEqual([]);
  });
});

describe('version bump check', () => {
  const git = (root: string, ...args: string[]) => execFileSync('git', args, { cwd: root, stdio: 'pipe' });

  function repo(): string {
    const root = mkdtempSync(join(tmpdir(), 'bump-'));
    git(root, 'init', '-q', '-b', 'main');
    git(root, 'config', 'user.email', 't@example.com');
    git(root, 'config', 'user.name', 't');
    write(root, {
      'datasets/d/a/task.toml': toml('1.0.0'),
      'datasets/d/a/instruction.md': 'a\n',
      'datasets/d/b/task.toml': toml(null),
      'datasets/d/b/instruction.md': 'b\n',
    });
    git(root, 'add', '.');
    git(root, 'commit', '-q', '-m', 'base');
    git(root, 'branch', 'base');
    return root;
  }

  it('fails a changed task without a bump and passes once bumped', () => {
    const root = repo();
    write(root, { 'datasets/d/a/instruction.md': 'a changed\n', 'datasets/d/b/instruction.md': 'b changed\n', 'datasets/d/c/task.toml': toml('1.0.0') });
    git(root, 'add', '.');
    git(root, 'commit', '-q', '-m', 'change');
    // b had no version at base, c is new: neither is checked.
    expect(bumpIssues(root, 'base').map((i) => i.task)).toEqual(['datasets/d/a']);
    write(root, { 'datasets/d/a/task.toml': toml('2.0.0') });
    git(root, 'commit', '-q', '-am', 'bump');
    expect(bumpIssues(root, 'base')).toEqual([]);
  });
});
