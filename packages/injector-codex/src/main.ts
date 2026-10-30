import { join } from 'node:path';
import { encode, filePending, handle, nodeRun, type CallEvent } from './index.js';

const STATE = process.env.TT_STATE ?? '/opt/tt/state';

async function main(): Promise<void> {
  const chunks: Buffer[] = [];
  for await (const c of process.stdin) chunks.push(c as Buffer);
  let e: CallEvent;
  try {
    e = JSON.parse(Buffer.concat(chunks).toString('utf8')) as CallEvent;
  } catch {
    return;
  }
  const answer = await handle(e, nodeRun, filePending(join(STATE, 'pending')));
  if (answer !== null) process.stdout.write(encode(answer));
}

void main();
