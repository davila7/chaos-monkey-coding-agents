import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

/** SPEC Appendix B.3, appended verbatim to every instruction.md. */
export const COMPLETION_CONTRACT = [
  'When you are done, write /app/STATUS.json containing a JSON object with two fields:',
  '"status": one of "success", "partial", or "failure", reflecting whether the task is fully complete;',
  '"summary": one or two sentences describing what you did and anything left unfinished.',
].join('\n');

const SEMVER = /^(\d+)\.(\d+)\.(\d+)$/;

/** A top-level key in one TOML table; enough for the flat string keys task files use. */
function tomlString(text: string, table: string | null, key: string): string | null {
  let current: string | null = null;
  for (const line of text.split('\n')) {
    const header = line.match(/^\s*\[([^\]]+)\]\s*(#.*)?$/);
    if (header) {
      current = header[1]!.trim();
      continue;
    }
    if (current !== table) continue;
    const m = line.match(new RegExp(`^\\s*${key}\\s*=\\s*"([^"]*)"`));
    if (m) return m[1]!;
  }
  return null;
}

/** `version` in the `[task]` table of task.toml (D-0012 item 1). */
export const taskVersion = (taskToml: string) => tomlString(taskToml, 'task', 'version');
export const chaosSchema = (chaosToml: string) => tomlString(chaosToml, null, 'schema');

export function parseSemver(v: string): [number, number, number] | null {
  const m = v.match(SEMVER);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

export function semverGreater(a: string, b: string): boolean {
  const x = parseSemver(a);
  const y = parseSemver(b);
  if (!x || !y) return false;
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i]! > y[i]!;
  return false;
}

export interface TaskFileIssue {
  rule: 'task-version' | 'chaos-schema' | 'chaos-poison' | 'instruction-contract';
  detail: string;
}

/**
 * SPEC 10.4 item 1 checks that read one task directory. Conformance probes are not benchmark
 * tasks and end with their own reporting instruction, so the completion contract is checked
 * only in benchmark datasets.
 */
export function taskFileIssues(dir: string, benchmark: boolean): TaskFileIssue[] {
  const issues: TaskFileIssue[] = [];
  const version = taskVersion(readFileSync(join(dir, 'task.toml'), 'utf8'));
  if (version === null) issues.push({ rule: 'task-version', detail: 'task.toml has no [task] version' });
  else if (!parseSemver(version)) issues.push({ rule: 'task-version', detail: `version "${version}" is not MAJOR.MINOR.PATCH` });
  const chaos = join(dir, 'chaos.toml');
  if (!existsSync(chaos)) issues.push({ rule: 'chaos-schema', detail: 'chaos.toml is missing' });
  else {
    const text = readFileSync(chaos, 'utf8');
    if (chaosSchema(text) !== 'tt-task/1') issues.push({ rule: 'chaos-schema', detail: 'chaos.toml schema is not "tt-task/1"' });
    if (benchmark && !/^\s*\[\[poison\]\]/m.test(text)) {
      issues.push({ rule: 'chaos-poison', detail: 'chaos.toml declares no poisonable resource (SPEC 10.3, D-0037)' });
    }
  }
  const instruction = join(dir, 'instruction.md');
  if (benchmark && (!existsSync(instruction) || !readFileSync(instruction, 'utf8').trimEnd().endsWith(COMPLETION_CONTRACT))) {
    issues.push({ rule: 'instruction-contract', detail: 'instruction.md does not end with the completion contract (SPEC B.3)' });
  }
  return issues;
}

function git(root: string, args: string[]): { ok: boolean; out: string } {
  const r = spawnSync('git', args, { cwd: root, encoding: 'utf8' });
  return { ok: r.status === 0, out: r.stdout ?? '' };
}

export interface BumpIssue {
  task: string;
  detail: string;
}

/**
 * Tasks changed since `base` whose version did not increase (D-0012: any change to a task
 * bumps its version). New tasks and deleted tasks are not checked.
 */
export function bumpIssues(root: string, base: string): BumpIssue[] {
  const diff = git(root, ['diff', '--name-only', `${base}...HEAD`]);
  if (!diff.ok) throw new Error(`git diff against ${base} failed`);
  const tasks = new Set<string>();
  for (const path of diff.out.split('\n').filter(Boolean)) {
    const parts = path.split('/');
    // datasets/<dataset>/<task>/...
    if (parts[0] === 'datasets' && parts.length >= 4 && existsSync(join(root, parts[0], parts[1]!, parts[2]!, 'task.toml'))) {
      tasks.add(parts.slice(0, 3).join('/'));
    }
  }
  const issues: BumpIssue[] = [];
  for (const task of [...tasks].sort()) {
    const before = git(root, ['show', `${base}:${task}/task.toml`]);
    if (!before.ok) continue;
    const old = taskVersion(before.out);
    const now = taskVersion(readFileSync(join(root, task, 'task.toml'), 'utf8'));
    if (old === null) continue; // the version field itself is being introduced
    if (now === null || !semverGreater(now, old)) issues.push({ task, detail: `changed without a version bump (${old} -> ${now ?? 'none'})` });
  }
  return issues;
}
