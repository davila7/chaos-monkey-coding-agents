// Single-file gateway for the proxy container image.
import { build } from 'esbuild';

await build({
  entryPoints: ['src/bin/gateway.ts'],
  outfile: 'dist/bin/gateway.mjs',
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
  banner: { js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);" },
});
