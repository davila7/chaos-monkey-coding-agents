// Lays out what the Harbor agent copies to /opt/tt:
//   bin/tt-decide.cjs   shared decision engine
//   fxh/index.cjs       the command fxh runs before and after each tool call
import { build } from 'esbuild';
import { copyFileSync, mkdirSync, rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/main.ts'],
  outfile: 'dist/tt/fxh/index.cjs',
  bundle: true,
  format: 'cjs',
  platform: 'node',
  // Task images get Node from the distribution package, as for the Claude Code and OpenCode agents.
  target: 'node18',
  legalComments: 'none',
  logLevel: 'warning',
});
mkdirSync('dist/tt/bin', { recursive: true });
copyFileSync('../fault-engine/dist/bin/tt-decide.cjs', 'dist/tt/bin/tt-decide.cjs');
