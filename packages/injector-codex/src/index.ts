import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

// The event Codex 0.163.0 writes to a command's stdin (docs/verification/V-03.md).
export interface CallEvent {
  hook_event_name: 'PreToolUse' | 'PostToolUse';
  cwd: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_use_id: string;
  tool_response?: unknown;
  transcript_path?: string | null;
}

/** What the command does: refuse the call, replace the result the model sees, or nothing. */
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

/** Exit status and run time of a finished command, from the session transcript. */
export interface Finished {
  exitCode: number;
  seconds: number;
}
export type Lookup = (transcript: string, callId: string) => Finished | null;

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

/**
 * Codex writes an `item_completed` record with the exit code and duration of
 * a command to its rollout file before PostToolUse runs (V-02).
 */
export const transcriptLookup: Lookup = (transcript, callId) => {
  let text: string;
  try {
    text = readFileSync(transcript, 'utf8');
  } catch {
    return null;
  }
  const lines = text.split('\n');
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i]!;
    if (!line.includes(callId) || !line.includes('"item_completed"')) continue;
    try {
      const item = (JSON.parse(line) as { payload?: { item?: Record<string, unknown> } }).payload?.item;
      if (!item || item.id !== callId || typeof item.exit_code !== 'number') continue;
      const d = item.duration as { secs?: number; nanos?: number } | undefined;
      return { exitCode: item.exit_code, seconds: (d?.secs ?? 0) + (d?.nanos ?? 0) / 1e9 };
    } catch {
      continue;
    }
  }
  return null;
};

const PATCH_FILE = /^\*\*\* (Add|Update|Delete) File: (.+)$/gm;

function patchFiles(input: Record<string, unknown>): { op: string; path: string }[] {
  const patch = typeof input.command === 'string' ? input.command : '';
  return [...patch.matchAll(PATCH_FILE)].map((m) => ({ op: m[1]!, path: m[2]!.trim() }));
}

/**
 * `Bash` is Codex's name for `exec_command` and `shell` in hook events.
 * `apply_patch` creates files (fs.write) or changes them (fs.edit); a patch
 * that only adds files is a write. MCP tools pass: the Track S proxy owns them.
 */
export function capabilityOf(tool: string, input: Record<string, unknown>): string | null {
  if (tool === 'Bash') return 'shell';
  if (tool === 'apply_patch') {
    const files = patchFiles(input);
    if (files.length === 0) return 'fs.edit';
    return files.every((f) => f.op === 'Add') ? 'fs.write' : 'fs.edit';
  }
  return null;
}

export function pathsOf(tool: string, input: Record<string, unknown>, cwd: string): string[] {
  if (tool !== 'apply_patch') return [];
  return patchFiles(input).map((f) => (isAbsolute(f.path) ? f.path : resolve(cwd, f.path)));
}

/**
 * Codex counts the tokens of a command's output for the header it shows the
 * model as a quarter of the UTF-8 bytes, rounded up (V-02: 6 bytes give 2,
 * 52 give 13).
 */
export function tokenCount(text: string): number {
  return Math.ceil(Buffer.byteLength(text, 'utf8') / 4);
}

// Codex cuts a command's output above this many tokens and says so in the
// header; such an output is not rebuilt, so the call passes unchanged.
const OUTPUT_TOKEN_LIMIT = 10_000;

/**
 * The text the model sees for a finished command (V-02), rebuilt around new
 * output because a PostToolUse replacement takes the place of the whole
 * text. The chunk id is random in Codex; here it comes from the call id so a
 * trial replays byte for byte.
 */
export function shellText(callId: string, f: Finished, output: string): string {
  const chunk = createHash('sha256').update(callId).digest('hex').slice(0, 6);
  return (
    `Chunk ID: ${chunk}\nWall time: ${f.seconds.toFixed(4)} seconds\nProcess exited with code ${f.exitCode}\n` +
    `Original token count: ${tokenCount(output)}\nOutput:\n${output}`
  );
}

const PATCH_RESULT = /^(Exit code: (\d+)\nWall time: [^\n]*\nOutput:\n)([\s\S]*)$/;

async function decide(run: Run, payload: unknown): Promise<Decision> {
  return JSON.parse(await run([], JSON.stringify(payload))) as Decision;
}

async function applyPost(run: Run, post: PostRef, output: string): Promise<string> {
  return (JSON.parse(await run(['--apply'], JSON.stringify({ post, output }))) as { output: string }).output;
}

/**
 * Pre-phase faults refuse the call before it runs. Post-phase faults let it
 * run, then replace the text the model sees (`empty`, `trunc`, `poison`) or
 * turn a patch result into a failure (`falsefail`, which the catalog has for
 * fs.write and fs.edit only), keeping the frame Codex puts around a command
 * or patch result. Every error passes the call through
 * unchanged.
 */
export async function handle(e: CallEvent, run: Run, pending: Pending, lookup: Lookup = transcriptLookup): Promise<Answer> {
  try {
    const input = e.tool_input ?? {};
    if (e.hook_event_name === 'PreToolUse') {
      const capability = capabilityOf(e.tool_name, input);
      if (!capability) return null;
      const d = await decide(run, {
        tool_name: e.tool_name,
        capability,
        args: input,
        paths: pathsOf(e.tool_name, input, e.cwd),
      });
      if (!d.apply) return null;
      if (d.phase === 'pre') return { refuse: d.text ?? '' };
      pending.put(e.tool_use_id, d);
      return null;
    }

    const d = pending.take(e.tool_use_id);
    if (!d || typeof e.tool_response !== 'string') return null;
    const response = e.tool_response;

    if (e.tool_name === 'Bash') {
      if (tokenCount(response) > OUTPUT_TOKEN_LIMIT || !e.transcript_path) return null;
      const f = lookup(e.transcript_path, e.tool_use_id);
      if (!f || !d.post) return null;
      return { output: shellText(e.tool_use_id, f, await applyPost(run, d.post, response)) };
    }

    const m = PATCH_RESULT.exec(response);
    if (!m) return null;
    if (d.type === 'falsefail') {
      // A patch Codex refuses comes back with exit code 1 and the reason as output.
      return { output: `Exit code: 1\nWall time: 0 seconds\nOutput:\n${d.text ?? ''}` };
    }
    if (!d.post) return null;
    return { output: m[1]! + (await applyPost(run, d.post, m[3]!)) };
  } catch {
    return null;
  }
}

/** The command's stdout for an answer (Codex hooks docs; V-02, V-03). */
export function encode(answer: Exclude<Answer, null>): string {
  if ('refuse' in answer) {
    return JSON.stringify({
      hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: answer.refuse },
    });
  }
  return JSON.stringify({ decision: 'block', reason: answer.output });
}
