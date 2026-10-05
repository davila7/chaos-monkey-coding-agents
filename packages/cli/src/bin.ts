#!/usr/bin/env node
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
  default:
    console.error('usage: cmca lint [--root <dir>]');
    process.exit(2);
}
