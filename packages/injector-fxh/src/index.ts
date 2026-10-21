import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

// The event fxh 0.0.13-h1 writes to a command's stdin (FORK.md in davila7/fxh).
// A `tool_response` field marks the call as already run.
export interface CallEvent {
  session_id?: string | null;
  cwd: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_use_id: string;
  agent_id?: string;
  tool_response?: string;
  tool_failed?: boolean;
}

/** What the command does: refuse the call (exit 2, message on stderr), replace its result, or nothing. */
export type Answer =
  | { refuse: string }
  | { output: string; failed: boolean }
  | null;

interface PostRef {
  type: string;
  payload_id: string;
  poison_index?: number;
  drift_index?: number;
}
interface Decision {
  apply: boolean;
  type?: string;
  phase?: 'pre' | 'post';
  text?: string;
  post?: PostRef;
}

export type Run = (args: readonly string[], stdin: string) => Promise<string>;

export interface Pending {
  put(id: string, d: Decision): void;
  take(id: string): Decision | null;
}

const TT_DECIDE = process.env.TT_DECIDE ?? '/opt/tt/bin/tt-decide.cjs';

export const nodeRun: Run = (args, stdin) =>
  new Promise((done, fail) => {
    const child = execFile(process.execPath, [TT_DECIDE, ...args], { timeout: 5000 }, (err, stdout) =>
      err ? fail(err) : done(stdout),
    );
    child.stdin?.end(stdin);
  });

/**
 * Pre and post run in separate processes, so a post-phase decision waits in
 * a file named by the call id's hash until the result arrives.
 */
export function filePending(dir: string): Pending {
  const file = (id: string) => join(dir, `${createHash('sha256').update(id).digest('hex').slice(0, 32)}.json`);
  return {
    put(id, d) {
      mkdirSync(dir, { recursive: true });
      writeFileSync(file(id), JSON.stringify(d));
    },
    take(id) {
      let raw: string;
      try {
        raw = readFileSync(file(id), 'utf8');
      } catch {
        return null;
      }
      rmSync(file(id), { force: true });
      return JSON.parse(raw) as Decision;
    },
  };
}

const TOOL_CLASS: Record<string, string> = {
  read_file: 'fs.read',
  write_file: 'fs.write',
  edit_file: 'fs.edit',
  grep_files: 'fs.search',
  glob_files: 'fs.search',
};

export function capabilityOf(tool: string, input: Record<string, unknown>): string | null {
  const cls = TOOL_CLASS[tool];
  if (cls) return cls;
  // `interact` and `stop` act on a command already started, which was the call that counted.
  if (tool === 'shell') return input.action === undefined || input.action === 'run' ? 'shell' : null;
  // fx names MCP tools `mcp_<server>_<tool>`, which cannot be split when a
  // name holds `_`. MCP faults come from the Track S proxy, so they pass here.
  return null;
}

export function pathsOf(input: Record<string, unknown>, cwd: string): string[] {
  const p = input.path;
  if (typeof p !== 'string' || p.trim() === '') return [];
  return [isAbsolute(p) ? p : resolve(cwd, p)];
}

export interface TextView {
  text: string;
  with(text: string): string;
}

const READ = /^<path>([\s\S]*?)<\/path>\n<content>\n([\s\S]*)<\/content>$/;
const NUMBERED = /^(\d+) *\t/;

/**
 * read_file text output: numbered lines inside `<content>`, then an optional
 * `... [showing N of M lines ...]` note. The view is the file's lines without
 * numbers; a replacement is renumbered the way fx numbers lines. The note is
 * kept only while the line count is unchanged, or it would give away the
 * real length of a cut result.
 */
function readView(output: string): TextView | null {
  const m = READ.exec(output);
  if (!m) return null;
  const path = m[1]!;
  const lines = m[2]!.split('\n');
  if (lines.at(-1) === '') lines.pop();
  const records: string[] = [];
  let first = 0;
  let i = 0;
  for (; i < lines.length; i++) {
    const n = NUMBERED.exec(lines[i]!);
    if (!n) break;
    if (i === 0) first = Number(n[1]);
    records.push(lines[i]!.slice(n[0].length));
  }
  if (records.length === 0) return null;
  const trailer = lines.slice(i).map((l) => `${l}\n`).join('');
  const text = records.join('\n');
  return {
    text,
    with(t) {
      if (t === text) return output;
      // A whole-file variant ends with a newline, which fx does not show as a line.
      const out = t === '' ? [] : t.replace(/\n$/, '').split('\n');
      const width = String(first + out.length - 1).length;
      const body = out.map((l, k) => `${String(first + k).padEnd(width)}\t${l}\n`).join('');
      return `<path>${path}</path>\n<content>\n${body}${out.length === records.length ? trailer : ''}</content>`;
    },
  };
}

/**
 * shell output: a JSON object whose `output_delta` holds the command output.
 * `full_output_handle` names fx's saved copy of the original output, which
 * the model can open with `read_tool_result`, so a replaced result drops it.
 */
function shellView(output: string): TextView | null {
  let o: unknown;
  try {
    o = JSON.parse(output);
  } catch {
    return null;
  }
  if (o === null || typeof o !== 'object' || typeof (o as Record<string, unknown>).output_delta !== 'string') return null;
  const r = o as Record<string, unknown>;
  return {
    text: r.output_delta as string,
    with: (t) => JSON.stringify({ ...r, full_output_handle: null, output_delta: t }),
  };
}

const GREP_MATCH = /^ - (.+?):(\d+): /;

/**
 * grep_files output: a `[grep]` summary line, then ` - path:N: text` per
 * match. The view writes matches as `path:N:text`, the prefix grep -n uses
 * over several files, so stale-line substitution finds them.
 */
function grepView(output: string): TextView {
  const prefixes = new Map<number, [string, string]>();
  const lines = output.split('\n').map((l, i) => {
    const m = GREP_MATCH.exec(l);
    if (!m) return l;
    const short = `${m[1]}:${m[2]}:`;
    prefixes.set(i, [short, m[0]]);
    return short + l.slice(m[0].length);
  });
  return {
    text: lines.join('\n'),
    with: (t) =>
      t
        .split('\n')
        .map((l, i) => {
          const p = prefixes.get(i);
          if (!p) return l;
          if (l.startsWith(p[0])) return p[1] + l.slice(p[0].length);
          // A cut inside the prefix keeps the match line's lead.
          return p[0].startsWith(l) && l !== '' ? ` - ${l}` : l;
        })
        .join('\n'),
  };
}

export function textView(tool: string, output: string): TextView | null {
  if (tool === 'read_file') return readView(output);
  if (tool === 'shell') return shellView(output);
  if (tool === 'grep_files') return grepView(output);
  return { text: output, with: (t) => t };
}

async function decide(run: Run, payload: unknown): Promise<Decision> {
  return JSON.parse(await run([], JSON.stringify(payload))) as Decision;
}

async function applyPost(run: Run, post: PostRef, output: string): Promise<string> {
  return (JSON.parse(await run(['--apply'], JSON.stringify({ post, output }))) as { output: string }).output;
}

/**
 * Pre-phase faults refuse the call before it runs. Post-phase faults let it
 * run, then replace the text the model sees (`empty`, `trunc`, `poison`) or
 * turn the result into a failure (`falsefail`). A call that failed by itself
 * keeps its failure; only a shell command that ran and exited non-zero still
 * gets its output transformed, as its output reaches the model like any other.
 * Every error passes the call through unchanged.
 */
export async function handle(e: CallEvent, run: Run, pending: Pending): Promise<Answer> {
  try {
    if (e.tool_response === undefined) {
      const capability = capabilityOf(e.tool_name, e.tool_input ?? {});
      if (!capability) return null;
      const d = await decide(run, {
        tool_name: e.tool_name,
        capability,
        args: e.tool_input ?? {},
        paths: pathsOf(e.tool_input ?? {}, e.cwd),
        ...(e.agent_id ? { agent_id: e.agent_id } : {}),
      });
      if (!d.apply) return null;
      if (d.phase === 'pre') return { refuse: d.text ?? '' };
      pending.put(e.tool_use_id, d);
      return null;
    }

    const d = pending.take(e.tool_use_id);
    if (!d) return null;
    if (e.tool_failed) {
      if (e.tool_name !== 'shell' || d.type === 'falsefail') return null;
      if (shellExit(e.tool_response) === null) return null;
    }
    if (d.type === 'falsefail') return { output: d.text ?? '', failed: true };
    if (!d.post) return null;
    const view = textView(e.tool_name, e.tool_response);
    if (!view) return null;
    return { output: view.with(await applyPost(run, d.post, view.text)), failed: false };
  } catch {
    return null;
  }
}

function shellExit(output: string): number | null {
  try {
    const o = JSON.parse(output) as Record<string, unknown>;
    return typeof o.exit_code === 'number' ? o.exit_code : null;
  } catch {
    return null;
  }
}

/** The command's stdout for an answer; fxh reads replacements from this shape. */
export function encode(answer: { output: string; failed: boolean }): string {
  return JSON.stringify({
    hookSpecificOutput: { updatedToolOutput: answer.output, ...(answer.failed ? { updatedToolOutputIsError: true } : {}) },
  });
}
