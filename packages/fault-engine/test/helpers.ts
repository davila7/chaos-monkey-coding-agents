import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { loadCatalog, loadProfile, resolveEngineConfig } from '../src/load.js';
import type { EngineConfig, EngineConfigInput, Profile } from '../src/schemas.js';
import { FAULT_TYPES, type CallSignature } from '../src/types.js';

export const ROOT = fileURLToPath(new URL('../../../', import.meta.url));
export const PKG = fileURLToPath(new URL('../', import.meta.url));

export const catalog = loadCatalog(`${PKG}catalog/v1.json`);
export const profile = (name: string): Profile => loadProfile(`${ROOT}profiles/${name}.yaml`);

export function config(over: Partial<EngineConfigInput> = {}): EngineConfig {
  return resolveEngineConfig({
    schema: 'tt-engine/1',
    seed: 'seed-0',
    task_id: 't-001',
    attempt: 0,
    harness: 'h@1',
    layer: 'native',
    profile: profile('moderate'),
    parity_set: [...FAULT_TYPES],
    catalog_version: 'v1',
    task: { schema: 'tt-task/1' },
    ...over,
  });
}

export function sig(over: Partial<CallSignature> = {}): CallSignature {
  return {
    taskId: 't-001',
    attempt: 0,
    harness: 'h@1',
    toolName: 'Read',
    capability: 'fs.read',
    canonicalArgs: '{"path":"src/a.ts"}',
    ...over,
  };
}

export function profileWith(base: Profile, over: Partial<Profile>): Profile {
  return { ...base, ...over };
}

export const readJson = (p: string): unknown => JSON.parse(readFileSync(p, 'utf8'));
