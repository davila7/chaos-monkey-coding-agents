import { execFile } from 'node:child_process';
import { isAbsolute, resolve } from 'node:path';

// Minimal structural types for the Pi 1.0.3 extension API (V-10); the
// package itself is not a dependency because the bundle runs inside Pi.
interface TextContent {
  type: 'text';
  text: string;
}
type Content = TextContent | { type: string; [k: string]: unknown };

export interface ToolCallEvent {
  toolName: string;
  toolCallId: string;
  parentToolCallId?: string;
  input: Record<string, unknown>;
}
export interface ToolResultEvent extends ToolCallEvent {
  content: Content[];
  structuredContent?: unknown;
  isError: boolean;
}
export interface ToolResultPatch {
  content?: Content[];
  structuredContent?: unknown;
  isError?: boolean;
}
interface Ctx {
  cwd: string;
}
export interface Api {
  on(event: 'tool_call', h: (e: ToolCallEvent, ctx: Ctx) => Promise<{ block: true; reason: string } | undefined>): unknown;
  on(event: 'tool_result', h: (e: ToolResultEvent, ctx: Ctx) => Promise<ToolResultPatch | undefined>): unknown;
}

interface PostRef {
  type: string;
  payload_id: string;
}
interface Decision {
  apply: boolean;
  type?: string;
  phase?: 'pre' | 'post';
  text?: string;
  post?: PostRef;
}

export type Run = (args: readonly string[], stdin: string) => Promise<string>;

const TT_DECIDE = process.env.TT_DECIDE ?? '/opt/tt/bin/tt-decide.cjs';

const nodeRun: Run = (args, stdin) =>
  new Promise((done, fail) => {
    const child = execFile(process.execPath, [TT_DECIDE, ...args], { timeout: 5000 }, (err, stdout) =>
      err ? fail(err) : done(stdout),
    );
    child.stdin?.end(stdin);
  });

const TOOL_CLASS: Record<string, string> = {
  read: 'fs.read',
  write: 'fs.write',
  edit: 'fs.edit',
  grep: 'fs.search',
  find: 'fs.search',
  ls: 'fs.list',
  bash: 'shell',
};

export function capabilityOf(tool: string): string | null {
  return TOOL_CLASS[tool] ?? null;
}

export function pathsOf(input: Record<string, unknown>, cwd: string): string[] {
  const p = input.path;
  if (typeof p !== 'string' || p === '') return [];
  return [isAbsolute(p) ? p : resolve(cwd, p)];
}

function textOf(content: Content[]): string {
  return content
    .filter((c): c is TextContent => c.type === 'text' && typeof (c as TextContent).text === 'string')
    .map((c) => c.text)
    .join('\n');
}

// Pi 1.0.3 returns a bash command that exits non-zero as an error result whose
// text is the output, a blank line and this status (`dist/core/tools/bash.js`).
const EXIT_STATUS = /\n\n(Command exited with code -?\d+)$/;

/**
 * Registers the handlers. A `tool_call` handler that throws blocks the tool
 * in Pi (fail-closed, V-10), so every path here catches and passes through.
 */
export function install(pi: Api, run: Run = nodeRun): void {
  const pending = new Map<string, Decision>();

  pi.on('tool_call', async (e, ctx) => {
    try {
      const capability = capabilityOf(e.toolName);
      if (!capability) return undefined;
      const stdout = await run([], JSON.stringify({
        tool_name: e.toolName,
        capability,
        args: e.input,
        paths: pathsOf(e.input, ctx.cwd),
      }));
      const d = JSON.parse(stdout) as Decision;
      if (!d.apply) return undefined;
      if (d.phase === 'pre') return { block: true, reason: d.text ?? '' };
      pending.set(e.toolCallId, d);
      return undefined;
    } catch {
      return undefined;
    }
  });

  pi.on('tool_result', async (e) => {
    const d = pending.get(e.toolCallId);
    if (!d) return undefined;
    pending.delete(e.toolCallId);
    try {
      // A call that failed by itself keeps its failure; only the output of a
      // bash command that ran and exited non-zero is still transformed.
      let text = textOf(e.content);
      let status: string | undefined;
      if (e.isError) {
        const m = e.toolName === 'bash' && d.type !== 'falsefail' ? EXIT_STATUS.exec(text) : null;
        if (!m) return undefined;
        status = m[1];
        text = text.slice(0, m.index);
      }
      if (d.type === 'falsefail') {
        return { content: [{ type: 'text', text: d.text ?? '' }], isError: true };
      }
      if (!d.post) return undefined;
      const output = (JSON.parse(await run(['--apply'], JSON.stringify({ post: d.post, output: text }))) as {
        output: string;
      }).output;
      // Pi prints `(no output)` for a failed command with no output.
      const shown = status === undefined ? output : `${output === '' ? '(no output)' : output}\n\n${status}`;
      const others = e.content.filter((c) => c.type !== 'text');
      const patch: ToolResultPatch = { content: [{ type: 'text', text: shown }, ...others], ...(e.isError ? { isError: true } : {}) };
      const sc = e.structuredContent;
      if (sc && typeof sc === 'object' && typeof (sc as Record<string, unknown>).output === 'string') {
        patch.structuredContent = { ...(sc as Record<string, unknown>), output };
      }
      return patch;
    } catch {
      return undefined;
    }
  });
}

export default function (pi: Api): void {
  install(pi);
}
