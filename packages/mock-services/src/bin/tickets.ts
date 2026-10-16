import { FixtureSchema, TicketStore, ticketsService } from '../tickets.js';
import { run } from './run.js';

run('tickets', (f) => ticketsService(new TicketStore(FixtureSchema.parse(f))));
