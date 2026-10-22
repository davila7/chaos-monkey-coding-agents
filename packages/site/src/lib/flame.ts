/** Frame count and step of the flame in public/monkey.svg (scripts/gen-monkey.mjs). */
export const FLAME_FRAMES = 12;
export const FLAME_MS = 85;

/**
 * A still of flame frame `k`: Chrome and Safari never run animations inside an SVG favicon,
 * so the tab icon is animated by swapping stills instead.
 */
export function flameFrame(svg: string, k: number): string {
  let i = -1;
  return svg
    .replace(/<style>[\s\S]*?<\/style>/, '<style>.f,.e{opacity:0}.f.k{opacity:1}.glow{opacity:.7}</style>')
    .replace(/<g class="f[^"]*"/g, () => (++i === k ? '<g class="f k"' : '<g class="f"'));
}
