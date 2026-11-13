import { resolveEngineConfig } from '/repo/packages/fault-engine/dist/index.js';
import { writeFileSync } from 'node:fs';
// 58,538 bytes; the `port` line sits past the first 30,000 characters that Claude Code keeps in `stdout`.
const big = ['host = db-a', ...Array.from({ length: 1500 }, (_, i) => `replica_${String(i).padStart(4, '0')} = node-${String(i).padStart(4, '0')}.west.internal`), 'port = 5432', 'region = west', ''].join('\n');
writeFileSync('/work/big.conf', big);
const base = (profile, task = { schema: 'tt-task/1' }, extra = {}) => resolveEngineConfig({
  schema: 'tt-engine/1', seed: 'v01-persisted', task_id: 'probe', attempt: 0, harness: 'claude-code', layer: 'native',
  profile: { schema: 'tt-profile/2', name: 'probe', max_applied_per_trial: 1, persistence: { transient: 1 }, ...profile },
  parity_set: ['deny', 'err', 'empty', 'trunc', 'falsefail', 'poison'], catalog_version: 'v1', task, ...extra,
});
const out = '/work/cfg';
writeFileSync(`${out}/none.json`, JSON.stringify(base({ base_rate: 0, max_applied_per_trial: 0 })));
writeFileSync(`${out}/trunc.json`, JSON.stringify(base({ base_rate: 1, weights: { trunc: 1 } })));
writeFileSync(`${out}/empty.json`, JSON.stringify(base({ base_rate: 1, weights: { empty: 1 } })));
writeFileSync(`${out}/poison.json`, JSON.stringify(base({ base_rate: 0, targeted: { poison: 1 } },
  { schema: 'tt-task/1', poison: [{ tool: 'shell', source: '/app/big.conf', variant: 'variants/big.conf', token: 'tok-123456' }] },
  { variants: { 'variants/big.conf': big.replace('port = 5432', 'port = 6543 # tok-123456') }, sources: { 'variants/big.conf': big } })));
