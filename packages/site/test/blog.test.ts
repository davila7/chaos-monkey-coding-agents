import { describe, expect, it } from 'vitest';
import { loadPosts, parsePost } from '../src/lib/blog';

describe('blog posts', () => {
  const posts = loadPosts();

  it('parse, and have unique slugs', () => {
    expect(posts.length).toBeGreaterThan(0);
    expect(new Set(posts.map((p) => p.slug)).size).toBe(posts.length);
  });

  it('follow the documentation style: no em or en dashes', () => {
    for (const p of posts) expect(p.markdown + p.title + p.summary).not.toMatch(/[–—]/);
  });

  it('reference only images that exist in public/', async () => {
    const { existsSync } = await import('node:fs');
    for (const p of posts) {
      for (const [, src] of p.markdown.matchAll(/!\[[^\]]*\]\((\/[^)]+)\)/g)) {
        expect(existsSync(`public${src}`), src).toBe(true);
      }
    }
  });
});

describe('parsePost', () => {
  it('strips the date prefix to form the slug', () => {
    const p = parsePost('2026-01-02-hello.md', '---\ntitle: Hi\ndate: 2026-01-02\nsummary: S\n---\nBody\n');
    expect(p.slug).toBe('hello');
  });

  it('rejects a file whose name does not match its date', () => {
    expect(() => parsePost('2026-01-03-hello.md', '---\ntitle: Hi\ndate: 2026-01-02\nsummary: S\n---\nBody\n')).toThrow(/date/);
  });
});
