import { describe, expect, it } from 'vitest';
import { paretoFront, rankBands } from '../src/lib/bands';

const iv = (value: number, hw: number) => ({ value, lo: value - hw, hi: value + hw });

describe('rankBands', () => {
  it('puts overlapping intervals in one band', () => {
    expect(rankBands([iv(0.6, 0.05), iv(0.58, 0.05), iv(0.4, 0.05)])).toEqual([1, 1, 2]);
  });

  it('starts a new band against the band head, not the previous row', () => {
    // 0.50 overlaps 0.56 but not 0.62, so it opens band 2 even though 0.56 is in band 1.
    expect(rankBands([iv(0.62, 0.03), iv(0.56, 0.04), iv(0.5, 0.04)])).toEqual([1, 1, 2]);
  });

  it('is independent of input order', () => {
    const a = [iv(0.3, 0.02), iv(0.7, 0.02), iv(0.5, 0.02)];
    expect(rankBands(a)).toEqual([3, 1, 2]);
  });

  it('handles an empty board', () => {
    expect(rankBands([])).toEqual([]);
  });
});

describe('paretoFront', () => {
  it('keeps configs not beaten on both cost and success', () => {
    const front = paretoFront([
      { id: 'cheap', x: 0.5, y: 0.4 },
      { id: 'dominated', x: 1.0, y: 0.35 },
      { id: 'best', x: 2.0, y: 0.7 },
      { id: 'mid', x: 1.2, y: 0.55 },
    ]);
    expect(front).toEqual(['cheap', 'mid', 'best']);
  });
});
