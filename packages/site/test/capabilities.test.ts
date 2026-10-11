import { describe, expect, it } from 'vitest';
import { type Capabilities, grid, loadCapabilities } from '../src/lib/capabilities';

describe('committed capability files', () => {
  const caps = loadCapabilities();

  it('parse, one per harness version', () => {
    expect(caps.length).toBeGreaterThan(0);
    expect(new Set(caps.map((c) => `${c.harness}@${c.version}`)).size).toBe(caps.length);
  });

  it('every parity gap is a gap cell in the grid', () => {
    for (const c of caps) {
      const g = grid(caps, c);
      for (const p of c.parity_gaps) {
        const cell = g.cells[g.types.indexOf(p.type)]![g.classes.indexOf(p.capability)]!;
        expect(cell).toMatchObject({ state: 'gap', reason: p.reason });
      }
    }
  });
});

describe('grid', () => {
  const cap = (classes: Capabilities['faults'][string]['classes']): Capabilities => ({
    schema: 'tt-capabilities/1',
    harness: 'h',
    version: '1',
    generated_at: '',
    tool_map: {},
    faults: { err: { supported: true, delivered_as: 'tool_result', attribution_visible: true, runs_passed: 3, classes } },
    parity_set: ['err'],
    parity_gaps: [],
    crash_behavior: 'fail_open',
    injector_p95_ms: 1,
  });
  const r = (runs_passed: number, exposed: boolean, gap?: string) => ({ runs: 3, runs_passed, exposed, attribution_visible: false, gap });

  it('classifies each cell', () => {
    const c = cap({ 'fs.read': r(3, true), 'fs.edit': r(0, true, 'reason'), 'fs.search': r(0, false), shell: r(2, true) });
    const other = cap({ 'fs.list': r(0, false), 'fs.write': r(3, true) });
    other.harness = 'o';
    other.faults.empty = { ...other.faults.err!, classes: { 'fs.write': r(3, true) } };
    const g = grid([c, other], c);
    expect(g.classes).toEqual(['fs.read', 'fs.write', 'fs.edit', 'fs.search', 'fs.list', 'shell']);
    // fs.write and fs.list are absent from c's err entry but present in another file's: not tested, not n/a.
    expect(g.cells[0]!.map((x) => x.state)).toEqual(['delivered', 'not_tested', 'gap', 'not_tested', 'not_tested', 'failed']);
    expect(grid([c, other], other).cells[1]!.map((x) => x.state)).toEqual(['n/a', 'delivered', 'n/a', 'n/a', 'n/a', 'n/a']);
  });
});
