import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { basename, join, relative } from 'node:path';
import { parse } from 'acorn';
import { simple } from 'acorn-walk';
import { bannedHits } from './words.js';

export interface LintIssue {
  rule: 'banned-word' | 'canary-missing' | 'canary-leak';
  file: string;
  detail: string;
}

/**
 * Strings mandated by the SPEC 9.5 telemetry schema (record field names and
 * values). They never reach the agent through a tool result; see DECISIONS.md
 * D-0004 for the open question on renaming them.
 */
export const TELEMETRY_ALLOWLIST = new Set(['inject', 'injector_latency_ms']);

/** Files under each task directory that are copied into the agent container. */
const AGENT_VISIBLE = (rel: string) => rel === 'instruction.md' || rel.startsWith('environment/');
/** Files the agent never sees; each must carry the canary. */
const NEEDS_CANARY = (rel: string) =>
  rel === 'task.toml' || rel === 'chaos.toml' || rel.startsWith('solution/') || rel.startsWith('tests/');

function walk(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const out: string[] = [];
  for (const name of readdirSync(dir).sort()) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

const isText = (buf: Buffer) => !buf.subarray(0, 8000).includes(0);

export function readCanary(root: string): string {
  const m = readFileSync(join(root, 'datasets/CANARY'), 'utf8').match(
    /[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/,
  );
  if (!m) throw new Error('datasets/CANARY does not contain a UUIDv4');
  return m[0];
}

/** String literals, template chunks, and environment variable names in a JS bundle. */
export function bundleStrings(source: string, sourceType: 'script' | 'module' = 'script'): { strings: string[]; envNames: string[] } {
  const strings: string[] = [];
  const envNames = new Set<string>();
  const ast = parse(source, { ecmaVersion: 'latest', sourceType, allowHashBang: true });
  simple(ast, {
    Literal(n) {
      if (typeof n.value === 'string') strings.push(n.value);
    },
    TemplateElement(n) {
      strings.push(n.value.cooked ?? n.value.raw);
    },
    MemberExpression(n) {
      const obj = n.object;
      const isEnv =
        (obj.type === 'Identifier' && obj.name === 'env') ||
        (obj.type === 'MemberExpression' && obj.property.type === 'Identifier' && obj.property.name === 'env');
      if (!isEnv) return;
      if (!n.computed && n.property.type === 'Identifier') envNames.add(n.property.name);
      if (n.computed && n.property.type === 'Literal' && typeof n.property.value === 'string') envNames.add(n.property.value);
    },
  });
  return { strings, envNames: [...envNames] };
}

export interface LintOptions {
  /** Built single-file artifacts that are copied into agent containers. */
  artifacts?: string[];
}

export function defaultArtifacts(root: string): string[] {
  const pkgs = join(root, 'packages');
  const dists = existsSync(pkgs)
    ? readdirSync(pkgs)
        .filter((p) => p === 'fault-engine' || p.startsWith('injector-'))
        .map((p) => join(pkgs, p, p === 'fault-engine' ? 'dist/bin' : 'dist'))
    : [];
  return dists.flatMap(walk).filter((f) => /\.(c|m)?js$/.test(f));
}

export function lint(root: string, opts: LintOptions = {}): LintIssue[] {
  const issues: LintIssue[] = [];
  const rel = (p: string) => relative(root, p);
  const banned = (file: string, where: string, text: string, allow?: Set<string>) => {
    if (allow?.has(text)) return;
    for (const hit of bannedHits(text)) issues.push({ rule: 'banned-word', file, detail: `${where}: "${hit}"` });
  };

  const catalogDir = join(root, 'packages/fault-engine/catalog');
  for (const f of walk(catalogDir)) {
    banned(rel(f), 'file name', basename(f));
    const entries = JSON.parse(readFileSync(f, 'utf8')) as { id: string; text: string }[];
    for (const e of entries) {
      banned(rel(f), `entry ${e.id} id`, e.id);
      banned(rel(f), `entry ${e.id} text`, e.text);
    }
  }

  for (const f of opts.artifacts ?? defaultArtifacts(root)) {
    banned(rel(f), 'file name', basename(f));
    const { strings, envNames } = bundleStrings(readFileSync(f, 'utf8'), f.endsWith('.cjs') ? 'script' : 'module');
    for (const s of strings) banned(rel(f), 'string', s, TELEMETRY_ALLOWLIST);
    for (const e of envNames) banned(rel(f), 'environment variable', e);
  }

  const datasets = join(root, 'datasets');
  const canary = existsSync(join(datasets, 'CANARY')) ? readCanary(root) : null;
  const taskDirs = walk(datasets)
    .filter((f) => basename(f) === 'task.toml')
    .map((f) => join(f, '..'));
  for (const dir of taskDirs) {
    for (const f of walk(dir)) {
      const r = relative(dir, f).split('\\').join('/');
      const buf = readFileSync(f);
      const text = isText(buf) ? buf.toString('utf8') : '';
      if (AGENT_VISIBLE(r)) {
        banned(rel(f), 'path', r);
        banned(rel(f), 'content', text);
        if (canary && text.includes(canary)) issues.push({ rule: 'canary-leak', file: rel(f), detail: 'agent-visible file carries the canary' });
      } else if (NEEDS_CANARY(r) && canary && isText(buf) && !text.includes(canary)) {
        issues.push({ rule: 'canary-missing', file: rel(f), detail: 'file the agent never sees must carry the canary' });
      }
    }
  }
  return issues;
}
