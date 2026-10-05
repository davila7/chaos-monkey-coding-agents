// Lays out what the Harbor agent copies to /opt/tt:
//   bin/tt-decide.cjs   shared decision engine
//   pi/index.js         one ES module that Pi loads with `--extension`
import { build } from 'esbuild';
import { copyFileSync, mkdirSync, rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/index.ts'],
  outfile: 'dist/tt/pi/index.js',
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
});
mkdirSync('dist/tt/bin', { recursive: true });
copyFileSync('../fault-engine/dist/bin/tt-decide.cjs', 'dist/tt/bin/tt-decide.cjs');
