import type { Register } from 'claude-code';
import { handle, type CallEvent, type CallResult, type Next } from './core.js';

export const register: Register = (on) => {
  on('tool.call', async ($, e, next) => {
    const run = (argv: readonly string[], init: { stdin: string; timeoutMs: number }) => $.process.run(argv, init);
    return (await handle(e as unknown as CallEvent, next as unknown as Next, run)) as Awaited<ReturnType<typeof next>> & CallResult;
  });
};
