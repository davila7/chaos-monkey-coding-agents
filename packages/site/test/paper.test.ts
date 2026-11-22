import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { BIBTEX, PAPER } from '../src/lib/paper';

describe('paper page', () => {
  it('serves the PDF published on Zenodo (md5 recorded in D-0058)', () => {
    const pdf = readFileSync(join(process.cwd(), 'public', PAPER.pdf));
    expect(createHash('md5').update(pdf).digest('hex')).toBe('33a33f9b423d71319cc3662df91057d9');
  });

  it('shows the same BibTeX entry as README.md', () => {
    const readme = readFileSync(join(process.cwd(), '..', '..', 'README.md'), 'utf8');
    expect(readme).toContain(BIBTEX);
  });

  it('cites the concept DOI from CITATION.cff', () => {
    const cff = readFileSync(join(process.cwd(), '..', '..', 'CITATION.cff'), 'utf8');
    expect(cff).toContain(`doi: "${PAPER.doi}"`);
  });
});
