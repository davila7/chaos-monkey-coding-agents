import { build } from 'esbuild';

await build({
  entryPoints: ['src/bin/tt-decide.ts'],
  outfile: 'dist/bin/tt-decide.cjs',
  bundle: true,
  platform: 'node',
  target: 'node22',
  format: 'cjs',
  minify: false,
  legalComments: 'none',
  logLevel: 'warning',
});
