#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { lint } from './lint.js';

const [cmd, ...rest] = process.argv.slice(2);
const rootIdx = rest.indexOf('--root');
const root = resolve(rootIdx >= 0 ? (rest[rootIdx + 1] ?? '.') : process.env.INIT_CWD ?? '.');

switch (cmd) {
  case 'lint': {
    const issues = lint(root);
    for (const i of issues) console.error(`${i.rule}  ${i.file}  ${i.detail}`);
    console.log(issues.length === 0 ? 'lint: ok' : `lint: ${issues.length} issue(s)`);
    process.exit(issues.length === 0 ? 0 : 1);
  }
  case 'analyze': {
    // The analysis is Python (SPEC 9.7); this forwards to it and then checks any site data it
    // wrote against the site's zod schema through the site's own data tests.
    const args = rootIdx < 0 ? rest : rest.filter((_, i) => i !== rootIdx && i !== rootIdx + 1);
    const run = (bin: string, argv: string[]) => spawnSync(bin, argv, { cwd: root, stdio: 'inherit' }).status ?? 1;
    let status = run('uv', ['run', 'python', '-m', 'cmca_analysis', 'analyze', ...args]);
    if (status === 0 && args.includes('--site')) {
      status = run('pnpm', ['--dir', 'packages/site', 'exec', 'vitest', 'run', 'test/data.test.ts']);
    }
    process.exit(status);
  }
  default:
    console.error('usage: cmca lint [--root <dir>]\n       cmca analyze --release <name> --seed <seed> --evidence <dir>... --out <dir> [--site <file>]');
    process.exit(2);
}
