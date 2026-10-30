// Lays out what the Harbor agent copies to /opt/tt:
//   bridge/index.cjs   the loopback server Codex calls as its model provider
import { build } from 'esbuild';
import { rmSync } from 'node:fs';

rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/main.ts'],
  outfile: 'dist/tt/bridge/index.cjs',
  bundle: true,
  format: 'cjs',
  platform: 'node',
  // Codex installs need Node 22 (Harbor's Codex agent), so the bridge can target it.
  target: 'node22',
  legalComments: 'none',
  logLevel: 'warning',
});
