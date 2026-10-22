import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { FLAME_FRAMES, flameFrame } from '../src/lib/flame';

const svg = readFileSync(join(__dirname, '..', 'public', 'monkey.svg'), 'utf8');

describe('flameFrame', () => {
  it('matches the frame count of the committed banner', () => {
    expect(svg.match(/<g class="f[^"]*"/g)).toHaveLength(FLAME_FRAMES);
  });

  it('shows exactly frame k and drops the animations', () => {
    for (const k of [0, 5, FLAME_FRAMES - 1]) {
      const out = flameFrame(svg, k);
      const groups = out.match(/<g class="f[^"]*"/g)!;
      expect(groups.filter((g) => g.includes(' k')).length).toBe(1);
      expect(groups.indexOf('<g class="f k"')).toBe(k);
      expect(out).not.toContain('@keyframes');
    }
  });
});
