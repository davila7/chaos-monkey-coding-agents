import { mkdirSync, writeFileSync } from 'node:fs';
import { z } from 'zod';
import { ALL_SCHEMAS } from '../dist/schemas.js';

mkdirSync('schemas', { recursive: true });
for (const [name, schema] of Object.entries(ALL_SCHEMAS)) {
  const json = z.toJSONSchema(schema, { io: 'input', unrepresentable: 'any' });
  writeFileSync(`schemas/${name}.schema.json`, `${JSON.stringify(json, null, 2)}\n`);
}
