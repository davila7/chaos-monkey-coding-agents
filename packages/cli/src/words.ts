/** SPEC 7.2 banned list, as stems so inflections are caught too. */
export const BANNED_STEMS = ['chaos', 'fault', 'inject', 'benchmark', 'synthetic', 'simulat', 'monkey', 'cmca', 'hook'] as const;
export const BANNED_PHRASES = [['test', 'harness']] as const;

/** Splits on non-alphanumerics and camelCase boundaries, lowercased. */
export function tokens(text: string): string[] {
  return text
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

export function bannedHits(text: string): string[] {
  const t = tokens(text);
  const hits = new Set<string>();
  for (const tok of t) for (const stem of BANNED_STEMS) if (tok.startsWith(stem)) hits.add(tok);
  for (let i = 0; i + 1 < t.length; i++) {
    for (const [a, b] of BANNED_PHRASES) if (t[i] === a && t[i + 1]?.startsWith(b)) hits.add(`${a} ${b}`);
  }
  return [...hits];
}
