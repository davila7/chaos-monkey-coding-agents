// Generates public/monkey.svg: the banner monkey with an animated pixel flame.
// Coordinates are banner.png pixels so the SVG lines up with public/banner-text.png.
// Run: node scripts/gen-monkey.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const OUT = fileURLToPath(new URL('../public/monkey.svg', import.meta.url));

const WIDTH = 700;
const HEIGHT = 724;
const BG = '#060505';
const FACE = '#e4e3e3';

// Traced from banner.png (contours of the white mask, simplified to 2.5 px).
const FACE_PATH = [
  'M304,585 349,635 379,636 415,635 459,588 459,584Z',
  'M304,520 305,566 459,566 459,519 408,466 356,466Z',
  'M352,492 355,483 367,483 374,491 389,491 397,483 409,483 412,493 383,525Z',
  'M202,403 181,421 181,449 204,468Z',
  'M561,402 561,468 565,468 585,449 585,421Z',
  'M232,403 232,452 273,493 312,493 347,454 352,454 360,446 364,425 402,425 404,444 452,493 494,493 534,453 534,402 494,362 437,362 404,395 403,404 369,405 363,404 363,397 329,362 273,362Z',
  'M447,386 485,386 511,412 511,443 485,469 447,469 423,444 423,410Z',
  'M281,386 318,386 343,411 343,443 318,469 282,470 256,444 256,410Z',
  'M595,358 563,386 590,386 612,406 612,449 561,493 561,517 589,505 636,466 636,389Z',
  'M171,358 130,389 130,466 179,507 204,517 204,493 154,449 154,406 178,386 202,386 176,359Z',
].join(' ');

// Hair line: the lower edge of the flame in banner.png. The head is drawn over the
// flame in the background color, so the flame shows the spikes by occlusion.
const HEAD = [
  [204, 724], [204, 380], [216, 372], [232, 336], [262, 312], [284, 284], [300, 304], [334, 246],
  [346, 280], [390, 196], [430, 282], [442, 247], [478, 301], [490, 284], [508, 312],
  [532, 336], [550, 372], [560, 380], [560, 724],
];

// Average flame heat of banner.png per 12 px cell (0-9), from x=100, y=28.
const CELL = 12;
const X0 = 100;
const Y0 = 28;
const ENVELOPE = [
  '................................................',
  '.........................00.....................',
  '........................010.....................',
  '........................000......10.............',
  '..................11...0110......00.............',
  '.................1330..02220..000...............',
  '.................1320..0233200121...............',
  '..................110..0244310121...............',
  '.............00...01000245543100...0000.........',
  '............0220..1111235775310....00...........',
  '............1320.011124568764110...00...........',
  '............011001223456898642220..110..........',
  '........10...0.0122345679986422210011100........',
  '.....0.0220..0012334567899864223210121110..0....',
  '....0100110..012344567876897543331002210..121...',
  '....011.011..123455679853798765431001210..121...',
  '.....0..01210234566789721599875443101321..010...',
  '........123213456777985103899755542123320.......',
  '.......0234433467876872..1687776543245420.......',
  '...11..0256543579854651..0464588644456530.00....',
  '..011..0368655679732320...132378655578630000....',
  '...0000136887766751010....000156566788520.0.....',
  '....011136898753320..........023357898520010....',
  '...012223579852110............01147997532220....',
  '...123433579730..................15897543320....',
  '...02345577631...................02577654320....',
  '...0122467630.....................0157642210....',
  '....00014541.......................02542000.....',
  '........121.........................1210........',
  '.........0...........................0..........',
];
const COLS = ENVELOPE[0].length;
const ROWS = ENVELOPE.length;

const FRAMES = 12;
const FRAME_MS = 85;
const PALETTE = [
  // [min heat, color], hottest first
  [1.0, '#fff3b0'],
  [0.72, '#ffd23a'],
  [0.55, '#ffa020'],
  [0.38, '#ff6a14'],
  [0.22, '#e8380d'],
  [0.14, '#9e1f08'],
];

function insidePolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// Deterministic hash so the committed SVG is reproducible.
function hash(i, j) {
  let h = Math.imul(i, 374761393) ^ Math.imul(j, 668265263);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

// Value noise, periodic in y with period `py` lattice units so the animation loops.
function noise(x, y, py, seed) {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const fx = x - xi;
  const fy = y - yi;
  const sx = fx * fx * (3 - 2 * fx);
  const sy = fy * fy * (3 - 2 * fy);
  const v = (a, b) => hash(a + seed * 7919, ((b % py) + py) % py);
  const top = v(xi, yi) + (v(xi + 1, yi) - v(xi, yi)) * sx;
  const bot = v(xi, yi + 1) + (v(xi + 1, yi + 1) - v(xi, yi + 1)) * sx;
  return top + (bot - top) * sy;
}

function envelope() {
  const env = ENVELOPE.map((row) => [...row].map((c) => (c === '.' ? 0 : (Number(c) + 1) / 10)));
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const cx = X0 + i * CELL + CELL / 2;
      const cy = Y0 + j * CELL + CELL / 2;
      // Keep the flame burning behind the head so the hair line always has fire on it.
      if (insidePolygon(cx, cy, HEAD)) env[j][i] = Math.max(env[j][i], 0.95);
    }
  }
  // Let tongues reach one cell above their averaged extent.
  for (let j = 0; j < ROWS - 1; j++) {
    for (let i = 0; i < COLS; i++) env[j][i] = Math.max(env[j][i], env[j + 1][i] * 0.55);
  }
  return env;
}

function sampleRow(env, i, y) {
  const j = Math.floor(y);
  const f = y - j;
  const at = (r) => (r >= 0 && r < ROWS ? env[r][i] : r >= ROWS ? env[ROWS - 1][i] : 0);
  return at(j) * (1 - f) + at(j + 1) * f;
}

function frameCells(env, t) {
  // Noise scrolls upward and loops after one lattice period. The coarse octave
  // displaces the averaged flame vertically so tongues stretch and drop; the fine
  // octave varies the color inside them.
  const p1 = 6;
  const p2 = 12;
  const cells = [];
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const n1 = noise(i / 2.6, j / 2.5 + t * p1, p1, 1);
      const n2 = noise(i / 1.3, j / 1.3 + t * p2, p2, 2);
      const heat = sampleRow(env, i, j + 3.2 * (n1 - 0.4)) + 0.3 * (n2 - 0.5);
      const color = PALETTE.find(([min]) => heat >= min);
      if (color) cells.push([i, j, color[1]]);
    }
  }
  return cells;
}

// One path per color, merging horizontal runs of cells.
function cellsToPaths(cells) {
  const byColor = new Map();
  for (const [i, j, c] of cells) {
    if (!byColor.has(c)) byColor.set(c, new Map());
    const rows = byColor.get(c);
    if (!rows.has(j)) rows.set(j, []);
    rows.get(j).push(i);
  }
  const out = [];
  for (const [, , color] of PALETTE.map((p) => [0, 0, p[1]])) {
    const rows = byColor.get(color);
    if (!rows) continue;
    let d = '';
    for (const [j, xs] of [...rows.entries()].sort((a, b) => a[0] - b[0])) {
      xs.sort((a, b) => a - b);
      let start = xs[0];
      let prev = xs[0];
      for (const x of [...xs.slice(1), Infinity]) {
        if (x === prev + 1) {
          prev = x;
          continue;
        }
        const w = (prev - start + 1) * CELL;
        d += `M${X0 + start * CELL} ${Y0 + j * CELL}h${w}v${CELL}h-${w}z`;
        start = prev = x;
      }
    }
    out.push(`<path fill="${color}" d="${d}"/>`);
  }
  return out.join('');
}

// Sparks that rise and fade, positioned on the flame's outer edge.
const EMBERS = [
  [148, 238, 14, 0],
  [204, 156, 12, 0.5],
  [262, 120, 10, 1.1],
  [352, 70, 12, 0.3],
  [462, 96, 10, 0.8],
  [520, 152, 14, 1.4],
  [610, 200, 12, 0.2],
  [330, 168, 8, 1.7],
  [575, 270, 10, 1.0],
];

function build() {
  const env = envelope();
  const loop = FRAMES * FRAME_MS;
  const frames = [];
  for (let k = 0; k < FRAMES; k++) {
    const visible = k === 0 ? ' f0' : '';
    frames.push(
      `<g class="f${visible}" style="animation-delay:${k * FRAME_MS - loop}ms">${cellsToPaths(frameCells(env, k / FRAMES))}</g>`,
    );
  }
  const embers = EMBERS.map(
    ([x, y, s, delay]) =>
      `<rect class="e" x="${x}" y="${y}" width="${s}" height="${s}" fill="#ff7a1a" style="animation-delay:${delay}s"/>`,
  ).join('');
  const head = `M${HEAD.map(([x, y]) => `${x},${y}`).join(' ')}Z`;
  const pct = (100 / FRAMES).toFixed(3);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="${WIDTH}" height="${HEIGHT}" role="img" aria-label="Chaos monkey">
<style>
.f{opacity:0;animation:flame ${loop}ms step-end infinite}
@keyframes flame{0%{opacity:1}${pct}%{opacity:0}100%{opacity:0}}
.e{opacity:0;animation:ember 2.2s steps(11) infinite}
@keyframes ember{0%{opacity:0;transform:translateY(0)}10%{opacity:1}100%{opacity:0;transform:translateY(-110px)}}
.glow{animation:glow 1.7s ease-in-out infinite alternate}
@keyframes glow{from{opacity:.55}to{opacity:.85}}
@media (prefers-reduced-motion:reduce){.f,.e,.glow{animation:none}.f0{opacity:1}}
</style>
<defs><radialGradient id="g" cx="50%" cy="60%" r="50%"><stop offset="0" stop-color="#ff5a1a" stop-opacity=".35"/><stop offset="1" stop-color="#ff5a1a" stop-opacity="0"/></radialGradient></defs>
<ellipse class="glow" cx="382" cy="240" rx="320" ry="230" fill="url(#g)"/>
${frames.join('\n')}
${embers}
<path fill="${BG}" d="${head}"/>
<path fill="${FACE}" fill-rule="evenodd" d="${FACE_PATH}"/>
</svg>
`;
}

// Shared with scripts/gen-og-scene.mjs, which draws the same monkey in the link preview image.
export { build, BG, FACE, FACE_PATH, HEAD, PALETTE, cellsToPaths, envelope, frameCells, noise };

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFileSync(OUT, build());
}
