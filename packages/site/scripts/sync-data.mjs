// Copies committed artifacts from outside packages/site into data/, so the site builds from its
// own directory (Vercel Root Directory). test/sync.test.ts fails when a copy drifts from its source.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = join(dirname(fileURLToPath(import.meta.url)), '..');
const ROOT = join(SITE, '../..');

export function sources() {
  const pairs = [];
  const caps = join(ROOT, 'capabilities');
  for (const f of readdirSync(caps).filter((f) => f.endsWith('.json')).sort()) {
    pairs.push([join(caps, f), join(SITE, 'data/capabilities', f)]);
  }
  const smoke = join(ROOT, 'results/smoke');
  for (const run of readdirSync(smoke).sort()) {
    const summary = join(smoke, run, 'summary.json');
    if (existsSync(summary)) pairs.push([summary, join(SITE, 'data/smoke', `${run}.json`)]);
  }
  return pairs;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const [from, to] of sources()) {
    mkdirSync(dirname(to), { recursive: true });
    copyFileSync(from, to);
    console.log(`${from.slice(ROOT.length + 1)} -> ${to.slice(ROOT.length + 1)}`);
  }
}
