// Lays out what the Harbor agent copies to /opt/tt:
//   bin/tt-decide.cjs   shared decision engine
//   codex/index.cjs     the command Codex runs before and after each tool call
import { build } from 'esbuild';
import { copyFileSync, mkdirSync, rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/main.ts'],
  outfile: 'dist/tt/codex/index.cjs',
  bundle: true,
  format: 'cjs',
  platform: 'node',
  // Codex installs need Node 22 (Harbor's Codex agent).
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
});
mkdirSync('dist/tt/bin', { recursive: true });
copyFileSync('../fault-engine/dist/bin/tt-decide.cjs', 'dist/tt/bin/tt-decide.cjs');
