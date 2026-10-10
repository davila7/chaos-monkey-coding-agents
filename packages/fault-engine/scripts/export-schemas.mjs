import { mkdirSync, writeFileSync } from 'node:fs';
import { z } from 'zod';
import { ALL_SCHEMAS, EngineConfigSchema } from '../dist/schemas.js';

mkdirSync('schemas', { recursive: true });
for (const [name, schema] of Object.entries(ALL_SCHEMAS)) {
  const json = z.toJSONSchema(schema, { io: 'input', unrepresentable: 'any' });
  writeFileSync(`schemas/${name}.schema.json`, `${JSON.stringify(json, null, 2)}\n`);
}
// The resolved engine config, defaults applied: what an injector may read
// from /opt/tt/config.json. Harbor agents validate against it before upload.
writeFileSync(
  'schemas/tt-engine-1.resolved.schema.json',
  `${JSON.stringify(z.toJSONSchema(EngineConfigSchema, { io: 'output', unrepresentable: 'any' }), null, 2)}\n`,
);
