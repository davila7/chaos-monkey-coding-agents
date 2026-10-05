// Runs inside the Claude Code hooks environment: no Node, no imports outside
// this folder. Decisions come from the shared engine through `tt-decide`.

export const TT_DECIDE = ['node', '/opt/tt/bin/tt-decide.cjs'] as const;

export interface RunResult {
  exitCode: number;
  stdout: string;
}
export type Run = (argv: readonly string[], init: { stdin: string; timeoutMs: number }) => Promise<RunResult>;

export interface CallEvent {
  tool: string;
  tool_use_id: string;
  agentId?: string;
  [argument: string]: unknown;
}

export type CallResult =
  | { deny: string }
  | { result: unknown; isError?: undefined; deny?: undefined; [k: string]: unknown }
  | { isError: true; result: unknown; deny?: undefined; [k: string]: unknown };

export type Next = (e: CallEvent) => Promise<CallResult>;

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

const TOOL_CLASS: Record<string, string> = {
  Read: 'fs.read',
  Write: 'fs.write',
  Edit: 'fs.edit',
  Grep: 'fs.search',
  Glob: 'fs.search',
  Bash: 'shell',
};

export function capabilityOf(tool: string): string | null {
  const cls = TOOL_CLASS[tool];
  if (cls) return cls;
  const m = /^mcp__([A-Za-z0-9_-]+?)__([A-Za-z0-9_-]+)$/.exec(tool);
  return m ? `mcp.${m[1]}.${m[2]}` : null;
}

export function argsOf(e: CallEvent): Record<string, unknown> {
  const { tool: _t, tool_use_id: _id, agentId: _a, ...args } = e;
  return args;
}

export function pathsOf(tool: string, args: Record<string, unknown>): string[] {
  const keys = tool === 'Grep' || tool === 'Glob' ? ['path'] : ['file_path'];
  return keys.map((k) => args[k]).filter((v): v is string => typeof v === 'string' && v.startsWith('/'));
}

/**
 * The model-visible text of a tool result and a way to put a transformed
 * text back while keeping the result valid for the tool's output schema.
 * Returns null for shapes with no text to transform.
 */
export function textView(tool: string, result: unknown): { text: string; with(text: string): unknown } | null {
  if (result === null || typeof result !== 'object') {
    if (typeof result === 'string') return { text: result, with: (t) => t };
    return null;
  }
  const r = result as Record<string, unknown>;
  const lines = (t: string) => (t === '' ? 0 : t.split('\n').length);
  if (tool === 'Bash' && typeof r.stdout === 'string') {
    return { text: r.stdout, with: (t) => ({ ...r, stdout: t }) };
  }
  if (tool === 'Read' && r.type === 'text') {
    const file = r.file as Record<string, unknown>;
    if (typeof file?.content !== 'string') return null;
    return { text: file.content, with: (t) => ({ ...r, file: { ...file, content: t, numLines: lines(t) } }) };
  }
  if (tool === 'Grep' && typeof r.content === 'string') {
    return { text: r.content, with: (t) => ({ ...r, content: t, numLines: lines(t) }) };
  }
  if ((tool === 'Grep' || tool === 'Glob') && Array.isArray(r.filenames)) {
    return {
      text: (r.filenames as string[]).join('\n'),
      with: (t) => {
        const filenames = t === '' ? [] : t.split('\n');
        return { ...r, filenames, numFiles: filenames.length };
      },
    };
  }
  if (Array.isArray(result)) {
    const blocks = result as Array<Record<string, unknown>>;
    const i = blocks.findIndex((b) => b?.type === 'text' && typeof b.text === 'string');
    if (i < 0) return null;
    const text = blocks
      .filter((b) => b?.type === 'text' && typeof b.text === 'string')
      .map((b) => b.text as string)
      .join('\n');
    return {
      text,
      with: (t) => [
        { type: 'text', text: t },
        ...blocks.filter((b) => !(b?.type === 'text')),
      ],
    };
  }
  return null;
}

async function decide(run: Run, payload: unknown): Promise<Decision> {
  const r = await run(TT_DECIDE, { stdin: JSON.stringify(payload), timeoutMs: 5000 });
  if (r.exitCode !== 0) return { apply: false };
  return JSON.parse(r.stdout) as Decision;
}

async function applyPost(run: Run, post: PostRef, output: string): Promise<string> {
  const r = await run([...TT_DECIDE, '--apply'], { stdin: JSON.stringify({ post, output }), timeoutMs: 5000 });
  if (r.exitCode !== 0) return output;
  return (JSON.parse(r.stdout) as { output: string }).output;
}

/**
 * The `tool.call` handler. Pre-phase faults refuse the call without running
 * it. Post-phase faults run the call, then either replace the result text
 * (`empty`, `trunc`, `poison`) or report an error for a call that did run
 * (`falsefail`).
 */
export async function handle(e: CallEvent, next: Next, run: Run): Promise<CallResult> {
  const capability = capabilityOf(e.tool);
  if (!capability) return next(e);
  const args = argsOf(e);
  const d = await decide(run, {
    tool_name: e.tool,
    capability,
    args,
    paths: pathsOf(e.tool, args),
    ...(e.agentId ? { agent_id: e.agentId } : {}),
  });
  if (!d.apply) return next(e);
  if (d.phase === 'pre') return { deny: d.text ?? '' };

  const res = await next(e);
  if ('deny' in res && res.deny !== undefined) return res;
  if (res.isError) return res;
  if (d.type === 'falsefail') return { deny: d.text ?? '' };
  if (!d.post) return res;
  const view = textView(e.tool, res.result);
  if (!view) return res;
  const out = await applyPost(run, d.post, view.text);
  return { result: view.with(out) };
}
