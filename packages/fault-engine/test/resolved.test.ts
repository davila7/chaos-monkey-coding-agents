import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { DEFAULTED_KEYS, missingResolvedKeys } from '../src/bin/resolved.js';
import { PKG, config } from './helpers.js';

const read = (name: string) => JSON.parse(readFileSync(join(PKG, `schemas/${name}.schema.json`), 'utf8'));
const output = read('tt-engine-1.resolved');
const input = read('tt-engine-1');
const defaulted = (out: { required: string[] }, inp: { required?: string[] }) =>
  out.required.filter((k) => !(inp.required ?? []).includes(k)).sort();

describe('resolved engine config check', () => {
  it('lists exactly the keys the schema fills with defaults', () => {
    expect([...DEFAULTED_KEYS.root].sort()).toEqual(defaulted(output, input));
    expect([...DEFAULTED_KEYS.profile].sort()).toEqual(defaulted(output.properties.profile, input.properties.profile));
    expect([...DEFAULTED_KEYS.task].sort()).toEqual(defaulted(output.properties.task, input.properties.task));
  });

  it('accepts a resolved config and names what a raw one lacks', () => {
    const resolved = config();
    expect(missingResolvedKeys(resolved)).toEqual([]);
    const { workspace_root: _w, ...raw } = resolved;
    expect(missingResolvedKeys({ ...raw, task: { schema: 'tt-task/1' } })).toEqual([
      'workspace_root',
      'task.exposure',
      'task.poison',
      'task.non_idempotent',
      'task.drift',
      'task.alternatives',
      'task.exempt',
    ]);
    expect(missingResolvedKeys(null)).toEqual(['<root>']);
  });
});
