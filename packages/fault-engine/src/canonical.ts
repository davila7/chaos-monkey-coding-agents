import { posix } from 'node:path';
import type { CapabilityClass } from './types.js';

export function sortedJson(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(value).sort()) {
      const v = (value as Record<string, unknown>)[k];
      if (v !== undefined) out[k] = sortKeys(v);
    }
    return out;
  }
  return value;
}

/**
 * Workspace-relative POSIX path with no trailing slash. Paths outside the
 * workspace stay absolute so they never collide with workspace paths.
 */
export function canonicalPath(p: string, workspaceRoot: string): string {
  const root = posix.normalize(workspaceRoot.replace(/\\/g, '/')).replace(/\/+$/, '') || '/';
  const raw = p.replace(/\\/g, '/');
  const abs = posix.isAbsolute(raw) ? posix.normalize(raw) : posix.join(root, raw);
  const trimmed = abs.length > 1 ? abs.replace(/\/+$/, '') : abs;
  if (trimmed === root) return '.';
  const prefix = root === '/' ? '/' : `${root}/`;
  return trimmed.startsWith(prefix) ? trimmed.slice(prefix.length) : trimmed;
}

export function collapseWhitespace(cmd: string): string {
  return cmd.trim().replace(/\s+/g, ' ');
}

export interface CanonicalOptions {
  workspaceRoot: string;
  /** Argument keys that hold filesystem paths, as declared by the adapter. */
  pathKeys?: readonly string[];
  /** Argument key that holds the shell command string. */
  commandKey?: string;
}

/** SPEC 7.4 canonicalization of tool arguments. */
export function canonicalArgs(
  capability: CapabilityClass,
  args: unknown,
  opts: CanonicalOptions,
): string {
  if (capability === 'shell') {
    const key = opts.commandKey ?? 'command';
    const cmd =
      typeof args === 'string'
        ? args
        : args !== null && typeof args === 'object'
          ? (args as Record<string, unknown>)[key]
          : undefined;
    return typeof cmd === 'string' ? collapseWhitespace(cmd) : sortedJson(args ?? null);
  }
  if (capability.startsWith('mcp.') || args === null || typeof args !== 'object' || Array.isArray(args)) {
    return sortedJson(args ?? null);
  }
  const pathKeys = new Set(opts.pathKeys ?? ['path', 'file_path', 'filePath']);
  const copy: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) {
    copy[k] = pathKeys.has(k) && typeof v === 'string' ? canonicalPath(v, opts.workspaceRoot) : v;
  }
  return sortedJson(copy);
}
