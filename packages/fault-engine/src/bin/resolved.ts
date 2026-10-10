// tt-decide does not bundle zod (latency budget), so it checks structurally
// that defaults were applied: these are the keys the schema fills in.
// test/resolved.test.ts keeps them equal to the difference between the
// `required` lists of the resolved and the input JSON Schemas.
export const DEFAULTED_KEYS = {
  root: ['trial_id', 'parity_gaps', 'workspace_root', 'exempt_paths', 'variants'],
  profile: ['warmup_calls', 'persistence', 'weights', 'class_rate_multipliers'],
  task: ['exposure', 'poison', 'non_idempotent', 'drift', 'alternatives', 'exempt'],
} as const;

/** Paths of defaulted keys that `cfg` lacks; empty for a resolved config. */
export function missingResolvedKeys(cfg: unknown): string[] {
  const obj = (v: unknown): Record<string, unknown> | null =>
    v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
  const root = obj(cfg);
  if (!root) return ['<root>'];
  const missing: string[] = [];
  const check = (o: Record<string, unknown> | null, keys: readonly string[], prefix: string) => {
    if (!o) return void missing.push(prefix.slice(0, -1));
    for (const k of keys) if (!(k in o)) missing.push(prefix + k);
  };
  check(root, DEFAULTED_KEYS.root, '');
  if ('profile' in root) check(obj(root.profile), DEFAULTED_KEYS.profile, 'profile.');
  if ('task' in root) check(obj(root.task), DEFAULTED_KEYS.task, 'task.');
  return missing;
}
