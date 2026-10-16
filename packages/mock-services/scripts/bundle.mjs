// One self-contained file per service for its container image.
import { build } from 'esbuild';

await build({
  entryPoints: ['tickets', 'inventory', 'deploy', 'docs'].map((name) => ({ in: `src/bin/${name}.ts`, out: name })),
  outdir: 'dist/bin',
  outExtension: { '.js': '.mjs' },
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
  banner: { js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);" },
});
