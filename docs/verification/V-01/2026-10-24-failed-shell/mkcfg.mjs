import { resolveEngineConfig } from '../../../../packages/fault-engine/dist/index.js';
import { writeFileSync } from 'node:fs';
const base = (profile, task = { schema: 'tt-task/1' }, extra = {}) => resolveEngineConfig({
  schema: 'tt-engine/1', seed: 'v01-failed-shell', task_id: 'probe', attempt: 0, harness: 'claude-code', layer: 'native',
  profile: { schema: 'tt-profile/2', name: 'probe', max_applied_per_trial: 100, persistence: { transient: 1 }, ...profile },
  parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'], catalog_version: 'v1', task, ...extra,
});
const out = process.argv[2];
writeFileSync(`${out}/trunc.json`, JSON.stringify(base({ base_rate: 1, weights: { trunc: 1 } })));
writeFileSync(`${out}/empty.json`, JSON.stringify(base({ base_rate: 1, weights: { empty: 1 } })));
writeFileSync(`${out}/poison.json`, JSON.stringify(base({ base_rate: 0, targeted: { poison: 1 } },
  { schema: 'tt-task/1', poison: [{ tool: 'shell', source: '/app/db.conf', variant: 'variants/db.conf', token: 'tok-123456' }] },
  { variants: { 'variants/db.conf': 'host = db-a\nport = 6543 # tok-123456\nregion = west\n' }, sources: { 'variants/db.conf': 'host = db-a\nport = 5432\nregion = west\n' } })));
