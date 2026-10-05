import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { canonicalArgs, canonicalPath, sortedJson } from '../src/canonical.js';

describe('canonicalization', () => {
  it('normalizes paths relative to the workspace root', () => {
    expect(canonicalPath('/app/src/a.ts', '/app')).toBe('src/a.ts');
    expect(canonicalPath('src//b/../a.ts', '/app')).toBe('src/a.ts');
    expect(canonicalPath('/app/src/', '/app')).toBe('src');
    expect(canonicalPath('/app', '/app/')).toBe('.');
    expect(canonicalPath('src\\a.ts', '/app')).toBe('src/a.ts');
    expect(canonicalPath('/etc/passwd', '/app')).toBe('/etc/passwd');
    expect(canonicalPath('/application/x', '/app')).toBe('/application/x');
  });

  it('sorts keys at every depth', () => {
    expect(sortedJson({ b: 1, a: { d: [{ z: 1, y: 2 }], c: null } })).toBe('{"a":{"c":null,"d":[{"y":2,"z":1}]},"b":1}');
  });

  it('collapses shell whitespace and nothing else', () => {
    expect(canonicalArgs('shell', { command: '  ls   -la\n\tsrc ' }, { workspaceRoot: '/app' })).toBe('ls -la src');
    expect(canonicalArgs('shell', { command: "echo 'a  b'" }, { workspaceRoot: '/app' })).toBe("echo 'a b'");
  });

  it('gives the same result for equivalent fs arguments', () => {
    const a = canonicalArgs('fs.read', { path: '/app/x/y.txt', offset: 1 }, { workspaceRoot: '/app' });
    const b = canonicalArgs('fs.read', { offset: 1, path: 'x/y.txt' }, { workspaceRoot: '/app' });
    expect(a).toBe(b);
  });

  it('key order never changes MCP canonical args', () => {
    fc.assert(
      fc.property(fc.dictionary(fc.string(), fc.jsonValue()), (obj) => {
        const reversed = Object.fromEntries(Object.entries(obj).reverse());
        expect(canonicalArgs('mcp.s.t', reversed, { workspaceRoot: '/app' })).toBe(
          canonicalArgs('mcp.s.t', obj, { workspaceRoot: '/app' }),
        );
      }),
    );
  });
});
