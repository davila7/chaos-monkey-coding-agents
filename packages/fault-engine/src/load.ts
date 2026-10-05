import { readFileSync } from 'node:fs';
import { parse as parseYaml } from 'yaml';
import {
  CatalogSchema,
  EngineConfigSchema,
  HarnessConfigSchema,
  ProfileSchema,
  type Catalog,
  type EngineConfig,
  type EngineConfigInput,
  type HarnessConfig,
  type Profile,
} from './schemas.js';

export function loadProfile(path: string): Profile {
  return ProfileSchema.parse(parseYaml(readFileSync(path, 'utf8')));
}

export function loadHarnessConfig(path: string): HarnessConfig {
  return HarnessConfigSchema.parse(parseYaml(readFileSync(path, 'utf8')));
}

export function loadCatalog(path: string): Catalog {
  return CatalogSchema.parse(JSON.parse(readFileSync(path, 'utf8')));
}

export function resolveEngineConfig(input: EngineConfigInput): EngineConfig {
  return EngineConfigSchema.parse(input);
}
