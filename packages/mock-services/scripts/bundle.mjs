// One self-contained file per service for its container image.
import { build } from 'esbuild';

await build({
  entryPoints: ['src/bin/tickets.ts'],
  outfile: 'dist/bin/tickets.mjs',
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
  banner: { js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);" },
});
