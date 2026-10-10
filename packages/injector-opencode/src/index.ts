import { execFile } from 'node:child_process';
import { isAbsolute, resolve } from 'node:path';

// Minimal structural types for the OpenCode 1.18 plugin hooks (V-06); the
// package itself is not a dependency because the bundle runs inside OpenCode.
export interface BeforeInput {
  tool: string;
  sessionID: string;
  callID: string;
}
export interface AfterInput extends BeforeInput {
  args: unknown;
}
export interface AfterOutput {
  title: string;
  output: string;
  metadata: unknown;
}
export interface Hooks {
  'tool.execute.before': (input: BeforeInput, output: { args: unknown }) => Promise<void>;
  'tool.execute.after': (input: AfterInput, output: AfterOutput) => Promise<void>;
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

// OpenCode ships as a compiled binary, so process.execPath is OpenCode
// itself; tt-decide runs on the `node` that Harbor's install puts on PATH.
const nodeRun: Run = (args, stdin) =>
  new Promise((done, fail) => {
    const child = execFile('node', [TT_DECIDE, ...args], { timeout: 5000 }, (err, stdout) =>
      err ? fail(err) : done(stdout),
    );
    child.stdin?.end(stdin);
  });

const TOOL_CLASS: Record<string, string> = {
  read: 'fs.read',
  write: 'fs.write',
  edit: 'fs.edit',
  grep: 'fs.search',
  glob: 'fs.search',
  list: 'fs.list',
  bash: 'shell',
};

export function capabilityOf(tool: string): string | null {
  return TOOL_CLASS[tool] ?? null;
}

export function pathsOf(args: unknown, cwd: string): string[] {
  if (args === null || typeof args !== 'object') return [];
  const a = args as Record<string, unknown>;
  const p = typeof a.filePath === 'string' ? a.filePath : a.path;
  if (typeof p !== 'string' || p === '') return [];
  return [isAbsolute(p) ? p : resolve(cwd, p)];
}

/** A refusal the hook raises on purpose; every other error passes the call through. */
class Refusal extends Error {}

/**
 * Builds the hooks. A hook that throws turns the call into a tool error, so
 * only a scheduled refusal propagates; injector failures pass through.
 */
export function hooks(cwd: string, run: Run = nodeRun): Hooks {
  const pending = new Map<string, Decision>();

  return {
    async 'tool.execute.before'(input, output) {
      let d: Decision;
      try {
        const capability = capabilityOf(input.tool);
        if (!capability) return;
        d = JSON.parse(
          await run([], JSON.stringify({ tool_name: input.tool, capability, args: output.args, paths: pathsOf(output.args, cwd) })),
        ) as Decision;
      } catch {
        return;
      }
      if (!d.apply) return;
      if (d.phase === 'pre') throw new Refusal(d.text ?? '');
      pending.set(input.callID, d);
    },

    async 'tool.execute.after'(input, output) {
      const d = pending.get(input.callID);
      if (!d) return;
      pending.delete(input.callID);
      if (d.type === 'falsefail') throw new Refusal(d.text ?? '');
      if (!d.post) return;
      try {
        const res = JSON.parse(await run(['--apply'], JSON.stringify({ post: d.post, output: output.output }))) as { output: string };
        output.output = res.output;
      } catch {
        // Leave the real output in place.
      }
    },
  };
}
