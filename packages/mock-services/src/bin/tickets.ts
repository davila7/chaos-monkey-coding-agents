import { chmodSync, readFileSync, rmSync } from 'node:fs';
import { httpServer, writeSnapshot } from '../server.js';
import { FixtureSchema, TicketStore } from '../tickets.js';

const fixturePath = process.env.TICKETS_FIXTURE ?? '/srv/tickets/fixture.json';
const statePath = process.env.TICKETS_STATE ?? '/var/lib/tickets/state.json';
const port = Number(process.env.PORT ?? '8080');
// A socket path keeps the service off every network; only containers that mount it can call it.
const socket = process.env.TICKETS_SOCKET;

const store = new TicketStore(FixtureSchema.parse(JSON.parse(readFileSync(fixturePath, 'utf8'))));
// The verifier reads this file even when the agent made no writes.
writeSnapshot(store, statePath);
const server = httpServer(store, statePath);
if (socket) {
  rmSync(socket, { force: true });
  server.listen(socket, () => {
    chmodSync(socket, 0o666);
    process.stderr.write(`tickets listening on ${socket}\n`);
  });
} else {
  server.listen(port, '0.0.0.0', () => process.stderr.write(`tickets listening on :${port}\n`));
}
