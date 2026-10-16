import { chmodSync, readFileSync, rmSync } from 'node:fs';
import { httpServer, writeSnapshot, type Service } from '../server.js';

/** Starts one service from `<NAME>_FIXTURE`, writing its state to `<NAME>_STATE` after every write. */
export function run(name: string, make: (fixture: unknown) => Service): void {
  const env = (k: string) => process.env[`${name.toUpperCase()}_${k}`];
  const fixturePath = env('FIXTURE') ?? `/srv/${name}/fixture.json`;
  const statePath = env('STATE') ?? `/var/lib/${name}/state.json`;
  const port = Number(process.env.PORT ?? '8080');
  // A socket path keeps the service off every network; only containers that mount it can call it.
  const socket = env('SOCKET');

  const service = make(JSON.parse(readFileSync(fixturePath, 'utf8')));
  // The verifier reads this file even when the agent made no writes.
  writeSnapshot(service, statePath);
  const server = httpServer(service, statePath);
  if (socket) {
    rmSync(socket, { force: true });
    server.listen(socket, () => {
      chmodSync(socket, 0o666);
      process.stderr.write(`${name} listening on ${socket}\n`);
    });
  } else {
    server.listen(port, '0.0.0.0', () => process.stderr.write(`${name} listening on :${port}\n`));
  }
}
