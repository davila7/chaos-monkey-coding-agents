import { InventoryFixtureSchema, InventoryStore, inventoryService } from '../inventory.js';
import { run } from './run.js';

run('inventory', (f) => inventoryService(new InventoryStore(InventoryFixtureSchema.parse(f))));
