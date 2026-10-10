import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { SiteData } from './schema';

/**
 * Production builds read data/results.json, which `cmca analyze` writes from committed job
 * directories. SITE_DATA=sample swaps in data/sample.json for layout previews only.
 */
export function dataFile(): string {
  return process.env.SITE_DATA === 'sample' ? 'sample.json' : 'results.json';
}

export function loadSiteData(file = dataFile()): SiteData {
  const raw = JSON.parse(readFileSync(join(process.cwd(), 'data', file), 'utf8'));
  const data = SiteData.parse(raw);
  if (file === 'results.json' && data.kind === 'sample') {
    throw new Error('data/results.json has kind "sample"; sample numbers must never ship as results');
  }
  return data;
}
