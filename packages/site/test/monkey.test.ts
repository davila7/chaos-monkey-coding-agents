import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
// @ts-expect-error untyped build script
import { build } from '../scripts/gen-monkey.mjs';

const committed = readFileSync(new URL('../public/monkey.svg', import.meta.url), 'utf8');

describe('monkey.svg', () => {
  it('matches the generator output', () => {
    expect(committed).toBe(build());
  });

  it('stops the flame and shows one static frame under reduced motion', () => {
    expect(committed).toMatch(/@media \(prefers-reduced-motion:reduce\)\{\.f,\.e,\.glow\{animation:none\}\.f0\{opacity:1\}\}/);
    expect(committed.match(/class="f f0"/g)).toHaveLength(1);
  });

  it('loads nothing external', () => {
    expect(committed).not.toMatch(/href="(?!#)|<script|<image/);
  });
});
