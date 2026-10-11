import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { build } from 'esbuild';

const outfile = 'dist/bin/tt-decide.cjs';
const result = await build({
  entryPoints: ['src/bin/tt-decide.ts'],
  outfile,
  bundle: true,
  platform: 'node',
  target: 'node22',
  format: 'cjs',
  minify: false,
  legalComments: 'none',
  logLevel: 'warning',
  write: false,
});

// The injector test suites rebundle in parallel while others spawn the
// bundle; writing in place lets a spawn read a half-written file.
mkdirSync(dirname(outfile), { recursive: true });
const tmp = `${outfile}.${process.pid}.tmp`;
writeFileSync(tmp, result.outputFiles[0].contents);
renameSync(tmp, outfile);
