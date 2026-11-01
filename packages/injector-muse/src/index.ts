import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

// The event Muse Code 1.4.14 writes to a hook command's stdin (docs/verification/V-29.md).
export interface CallEvent {
  hook_event_name: 'PreToolUse' | 'PostToolUse' | 'PostToolUseFailure';
  session_id?: string;
  cwd: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_use_id: string;
  tool_response?: unknown;
  error?: string;
}

/** What the command does: refuse the call (exit 2, reason on stderr), replace the result the model sees, or nothing. */
export type Answer = { refuse: string } | { output: string } | null;

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

// Muse's default toolset (V-29). `bash_input` writes to a command already
// started, which was the call that counted. MCP tools belong to the Track S proxy.
const TOOL_CLASS: Record<string, string> = {
  read_file: 'fs.read',
  write_file: 'fs.write',
  edit_file: 'fs.edit',
  search: 'fs.search',
  bash: 'shell',
};

export function capabilityOf(tool: string): string | null {
  return TOOL_CLASS[tool] ?? null;
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

/** Muse's count of output tokens for a command: a quarter of the UTF-8 bytes, rounded up (V-29: 236 bytes 59, 49 bytes 13). */
export function tokenCount(text: string): number {
  return Math.ceil(Buffer.byteLength(text, 'utf8') / 4);
}

/**
 * bash result: a JSON object, indented by two spaces, whose `output` holds
 * the command output. A replacement keeps the object and its key order and
 * recounts the size fields.
 */
function shellView(response: string): TextView | null {
  let o: unknown;
  try {
    o = JSON.parse(response);
  } catch {
    return null;
  }
  if (o === null || typeof o !== 'object') return null;
  const r = o as Record<string, unknown>;
  if (typeof r.output !== 'string' || r.truncated === true) return null;
  return {
    text: r.output,
    with: (t) => {
      if (t === r.output) return response;
      return JSON.stringify(
        { ...r, output: t, original_output_bytes: Buffer.byteLength(t, 'utf8'), original_output_tokens: tokenCount(t) },
        null,
        2,
      );
    },
  };
}

const READ_HEAD = /^(Read text file [^\n]*\n)([\s\S]*)$/;
const NUMBERED = /^(\d+)\|/;

/**
 * read_file result: a `Read text file ...` line, then `N|text` per line. The
 * view is the file's lines without numbers; a replacement is renumbered the
 * same way. Lines after the numbered block are kept only while the line
 * count is unchanged, or they could give away the real length of a cut result.
 */
function readView(response: string): TextView | null {
  const m = READ_HEAD.exec(response);
  if (!m) return null;
  const lines = m[2]!.split('\n');
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
  const trailer = lines.slice(i);
  const text = records.join('\n');
  return {
    text,
    with(t) {
      if (t === text) return response;
      const out = t === '' ? [] : t.replace(/\n$/, '').split('\n');
      const body = out.map((l, k) => `${first + k}|${l}`);
      const rest = out.length === records.length ? trailer : [];
      return m[1]! + [...body, ...rest].join('\n');
    },
  };
}

export function textView(tool: string, response: string): TextView | null {
  if (tool === 'bash') return shellView(response);
  if (tool === 'read_file') return readView(response);
  if (tool === 'search') return { text: response, with: (t) => t };
  return null;
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
 * replace a write or edit result with the failure text (`falsefail`). A call
 * that fails arrives as PostToolUseFailure, whose output cannot replace the
 * result (V-29), so it passes unchanged, as does every error here.
 */
export async function handle(e: CallEvent, run: Run, pending: Pending): Promise<Answer> {
  try {
    const input = e.tool_input ?? {};
    if (e.hook_event_name === 'PreToolUse') {
      const capability = capabilityOf(e.tool_name);
      if (!capability) return null;
      const d = await decide(run, {
        tool_name: e.tool_name,
        capability,
        args: input,
        paths: pathsOf(input, e.cwd),
      });
      if (!d.apply) return null;
      if (d.phase === 'pre') return { refuse: d.text ?? '' };
      pending.put(e.tool_use_id, d);
      return null;
    }

    const d = pending.take(e.tool_use_id);
    if (!d || e.hook_event_name !== 'PostToolUse') return null;
    if (d.type === 'falsefail') return { output: d.text ?? '' };
    if (!d.post || typeof e.tool_response !== 'string') return null;
    const view = textView(e.tool_name, e.tool_response);
    if (!view) return null;
    return { output: view.with(await applyPost(run, d.post, view.text)) };
  } catch {
    return null;
  }
}

/** The hook's stdout for a replacement (V-29: `decision: block` replaces the result with `reason`). */
export function encode(answer: { output: string }): string {
  return JSON.stringify({ decision: 'block', reason: answer.output });
}
