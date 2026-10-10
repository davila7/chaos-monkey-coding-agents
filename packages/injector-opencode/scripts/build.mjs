// Lays out what the Harbor agent copies to /opt/tt:
//   bin/tt-decide.cjs   shared decision engine
//   oc/index.js         one ES module that OpenCode loads from its `plugin` config
import { build } from 'esbuild';
import { copyFileSync, mkdirSync, rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/plugin.ts'],
  outfile: 'dist/tt/oc/index.js',
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
});
mkdirSync('dist/tt/bin', { recursive: true });
copyFileSync('../fault-engine/dist/bin/tt-decide.cjs', 'dist/tt/bin/tt-decide.cjs');
