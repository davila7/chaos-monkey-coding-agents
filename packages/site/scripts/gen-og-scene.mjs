// Generates src/og/scene.svg: the static background of the link preview image.
// The flame monkey types at a desk while the room burns; the title is drawn over the
// empty left side by src/lib/og.tsx. The SVG is rasterized by resvg, so it uses no CSS.
// Run: node scripts/gen-og-scene.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { BG, FACE, FACE_PATH, HEAD, PALETTE, cellsToPaths, envelope, frameCells, noise } from './gen-monkey.mjs';

const OUT = fileURLToPath(new URL('../src/og/scene.svg', import.meta.url));

const W = 1200;
const H = 630;
const CELL = 12;
const COLS = W / CELL;
const ROWS = Math.ceil(H / CELL);

// Monkey placement: banner.png coordinates scaled so the glasses peek over the laptop.
const SCALE = 0.62;
const MX = 692;
const MY = 98;

const DESK_TOP = 470;
const DESK = { x0: 690, x1: 1170 };
const LID = { cx: 930, w: 236, top: 404 };

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// Flame height in px above the bottom edge. Low under the title, tall around the desk.
function height(x, layer) {
  if (layer === 'front') return 70 + 50 * smooth(560, 900, x);
  const left = 330 * Math.exp(-(((x - 676) / 54) ** 2));
  const right = 360 * Math.exp(-(((x - 1196) / 64) ** 2));
  return Math.max(left, right);
}

function fireCells(layer, seed) {
  const cells = [];
  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      const cx = i * CELL + CELL / 2;
      const top = height(cx, layer);
      if (top < 1) continue;
      const above = H - (j * CELL + CELL / 2);
      const n1 = noise(i / 2.4, j / 2.2, 1e6, seed);
      const n2 = noise(i / 1.2, j / 1.2, 1e6, seed + 1);
      const heat = 1.05 * (1 - above / (top * (0.75 + 0.5 * n1))) + 0.3 * (n2 - 0.5);
      const color = PALETTE.find(([min]) => heat >= min);
      if (color) cells.push([i, j, color[1]]);
    }
  }
  return cells;
}

function paths(cells) {
  const byColor = new Map(PALETTE.map(([, c]) => [c, []]));
  for (const [i, j, c] of cells) byColor.get(c).push([i, j]);
  return [...byColor]
    .filter(([, list]) => list.length)
    .map(([c, list]) => {
      list.sort((a, b) => a[1] - b[1] || a[0] - b[0]);
      let d = '';
      for (let k = 0; k < list.length; ) {
        const [i, j] = list[k];
        let n = 1;
        while (k + n < list.length && list[k + n][1] === j && list[k + n][0] === i + n) n++;
        d += `M${i * CELL} ${j * CELL}h${n * CELL}v${CELL}h-${n * CELL}z`;
        k += n;
      }
      return `<path fill="${c}" d="${d}"/>`;
    })
    .join('');
}

// Pixel paws on the keyboard, overlapping the lower corners of the lid.
function paw(x, flip) {
  const r = (dx, dy, w, h) => `M${flip ? x - dx - w : x + dx} ${DESK_TOP + dy}h${w}v${h}h-${w}z`;
  return [r(0, -22, 30, 16), r(-6, -14, 6, 8), r(0, -6, 6, 6), r(10, -6, 6, 6), r(20, -6, 6, 6)].join('');
}

const EMBERS = [
  [620, 300, 10],
  [700, 150, 12],
  [756, 238, 8],
  [1080, 120, 10],
  [1150, 210, 12],
  [1120, 330, 8],
  [520, 470, 8],
  [430, 520, 10],
  [800, 90, 8],
];

function build() {
  const head = `M${HEAD.map(([x, y]) => `${x},${y}`).join(' ')}Z`;
  const lidX = LID.cx - LID.w / 2;
  const pawL = lidX + 24;
  const pawR = lidX + LID.w - 24;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
<defs><radialGradient id="g" cx="50%" cy="100%" r="70%"><stop offset="0" stop-color="#ff5a1a" stop-opacity=".32"/><stop offset="1" stop-color="#ff5a1a" stop-opacity="0"/></radialGradient></defs>
<rect width="${W}" height="${H}" fill="${BG}"/>
<rect x="0" y="${H - 420}" width="${W}" height="420" fill="url(#g)"/>
${paths(fireCells('back', 3))}
<g transform="translate(${MX} ${MY}) scale(${SCALE})">
${cellsToPaths(frameCells(envelope(), 0))}
<path fill="${BG}" d="${head}"/>
<path fill="${FACE}" fill-rule="evenodd" d="${FACE_PATH}"/>
</g>
<path fill="#241c18" d="M${DESK.x0} ${DESK_TOP}h${DESK.x1 - DESK.x0}v${H - DESK_TOP}h-${DESK.x1 - DESK.x0}z"/>
<path fill="#3d2f27" d="M${DESK.x0 - 12} ${DESK_TOP}h${DESK.x1 - DESK.x0 + 24}v14h-${DESK.x1 - DESK.x0 + 24}z"/>
<path fill="#151110" stroke="#3d2f27" stroke-width="4" d="M${lidX} ${LID.top}h${LID.w}v${DESK_TOP - LID.top}h-${LID.w}z"/>
<path fill="#ff6a14" d="M${LID.cx - 6} ${LID.top + 22}h12v12h-12zM${LID.cx - 12} ${LID.top + 34}h24v12h-24z"/>
<path fill="#ffd23a" d="M${LID.cx - 6} ${LID.top + 40}h12v6h-12z"/>
<path fill="#2b2523" d="M${lidX - 16} ${DESK_TOP - 4}h${LID.w + 32}v8h-${LID.w + 32}z"/>
<path fill="${FACE}" d="${paw(pawL, false)}${paw(pawR, true)}"/>
${paths(fireCells('front', 5))}
${EMBERS.map(([x, y, s]) => `<rect x="${x}" y="${y}" width="${s}" height="${s}" fill="#ff7a1a"/>`).join('')}
</svg>
`;
}

export { build };

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeFileSync(OUT, build());
}
