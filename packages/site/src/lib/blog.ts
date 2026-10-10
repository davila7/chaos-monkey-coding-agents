import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { marked } from 'marked';
import { z } from 'zod';

const Front = z.object({
  title: z.string().min(1),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  summary: z.string().min(1),
});

export interface Post {
  slug: string;
  title: string;
  date: string;
  summary: string;
  markdown: string;
}

const DIR = () => join(process.cwd(), 'content/blog');

/** Files are named `YYYY-MM-DD-<slug>.md`; the date prefix is dropped from the URL. */
export function parsePost(file: string, source: string): Post {
  const m = source.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) throw new Error(`${file}: missing front matter`);
  const fields = Object.fromEntries(
    m[1]!.split('\n').map((line) => {
      const i = line.indexOf(':');
      return [line.slice(0, i).trim(), line.slice(i + 1).trim()];
    }),
  );
  const front = Front.parse(fields);
  const name = file.replace(/\.md$/, '');
  if (!name.startsWith(`${front.date}-`)) throw new Error(`${file}: file name must start with its date`);
  return { slug: name.slice(front.date.length + 1), ...front, markdown: m[2]! };
}

export function loadPosts(): Post[] {
  return readdirSync(DIR())
    .filter((f) => f.endsWith('.md'))
    .map((f) => parsePost(f, readFileSync(join(DIR(), f), 'utf8')))
    .sort((a, b) => b.date.localeCompare(a.date) || a.slug.localeCompare(b.slug));
}

export const renderPost = (p: Post) => marked.parse(p.markdown, { async: false });

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}
