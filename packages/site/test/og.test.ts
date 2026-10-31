import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
// @ts-expect-error untyped build script
import { build } from '../scripts/gen-og-scene.mjs';
import { loadPosts } from '../src/lib/blog';
import { titleSize } from '../src/lib/og';

const committed = readFileSync(new URL('../src/og/scene.svg', import.meta.url), 'utf8');

describe('og scene', () => {
  it('matches the generator output', () => {
    expect(committed).toBe(build());
  });

  it('is static and loads nothing external, since resvg rasterizes it', () => {
    expect(committed).not.toMatch(/<style|class=|href="(?!#)|<script|<image/);
    expect(committed).toMatch(/viewBox="0 0 1200 630"/);
  });
});

describe('titleSize', () => {
  it('keeps every post title within four lines of the 600 px column', () => {
    // JetBrains Mono advances 0.6 em per character.
    for (const { title } of loadPosts()) {
      const size = titleSize(title);
      const perLine = Math.floor(600 / (size * 0.6));
      let lines = 1;
      let used = 0;
      for (const word of title.split(' ')) {
        const need = used === 0 ? word.length : used + 1 + word.length;
        if (need > perLine) {
          lines++;
          used = word.length;
        } else used = need;
      }
      expect(lines, title).toBeLessThanOrEqual(4);
    }
  });
});
