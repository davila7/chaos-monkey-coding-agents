// Lays out what the Harbor agent copies to /opt/tt in the container:
//   bin/tt-decide.cjs                 shared decision engine
//   cc/.claude-plugin/plugin.json     Claude Code plugin manifest
//   cc/hooks/hooks.json, register.js, core.js
// Files are transpiled one by one, not bundled: the engine checks that
// `register` is declared in register.js and that `on(...)` and `$.process.run`
// appear literally at their call sites.
import { transform } from 'esbuild';
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';

const out = 'dist/tt';
rmSync('dist', { recursive: true, force: true });
mkdirSync(`${out}/bin`, { recursive: true });
mkdirSync(`${out}/cc/.claude-plugin`, { recursive: true });
mkdirSync(`${out}/cc/hooks`, { recursive: true });

for (const name of ['register', 'core']) {
  const src = readFileSync(`plugin/hooks/${name}.ts`, 'utf8');
  const { code } = await transform(src, { loader: 'ts', format: 'esm', target: 'es2022', legalComments: 'none' });
  writeFileSync(`${out}/cc/hooks/${name}.js`, code.replace(/^\/\/.*\n/gm, ''));
}
writeFileSync(`${out}/cc/hooks/hooks.json`, JSON.stringify({ modules: ['./register.js'] }) + '\n');
copyFileSync('plugin/.claude-plugin/plugin.json', `${out}/cc/.claude-plugin/plugin.json`);
copyFileSync('../fault-engine/dist/bin/tt-decide.cjs', `${out}/bin/tt-decide.cjs`);
