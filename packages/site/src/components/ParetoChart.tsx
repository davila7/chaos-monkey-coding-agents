import { paretoFront } from '@/lib/bands';
import { dollars, pct } from '@/lib/format';
import type { Row } from '@/lib/schema';
import { seriesColor } from './palette';

const W = 960;
const H = 420;
const M = { l: 56, r: 24, t: 20, b: 44 };

/** Tick step of 1, 2 or 5 times a power of ten. */
function niceStep(span: number, count: number): number {
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const f = raw / mag;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
}

export function ParetoChart({ rows }: { rows: Row[] }) {
  const pts = rows
    .map((r, i) => ({ r, i, x: r.metrics.dollars_per_success, y: r.metrics.faulted_success }))
    .filter((p): p is typeof p & { x: number } => p.x !== null);
  if (pts.length === 0) return <div className="chart empty">No cost data for this board.</div>;

  const step = niceStep(Math.max(...pts.map((p) => p.x)) * 1.1, 5);
  const xMax = Math.ceil((Math.max(...pts.map((p) => p.x)) * 1.1) / step) * step;
  const yMin = Math.max(0, Math.floor((Math.min(...pts.map((p) => p.y.lo)) - 0.05) * 10) / 10);
  const yMax = Math.min(1, Math.ceil((Math.max(...pts.map((p) => p.y.hi)) + 0.02) * 10) / 10);
  const sx = (v: number) => M.l + (v / xMax) * (W - M.l - M.r);
  const sy = (v: number) => H - M.b - ((v - yMin) / (yMax - yMin)) * (H - M.t - M.b);

  const front = new Set(paretoFront(pts.map((p) => ({ id: p.r.config_id, x: p.x, y: p.y.value }))));
  const frontPts = pts.filter((p) => front.has(p.r.config_id)).sort((a, b) => a.x - b.x);
  const yTicks = Array.from({ length: Math.round((yMax - yMin) * 10) + 1 }, (_, k) => yMin + k * 0.1);
  const xTicks = Array.from({ length: Math.round(xMax / step) }, (_, k) => step * (k + 1));

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Faulted success versus dollars per success">
        {yTicks.map((t) => (
          <g key={t}>
            <line className="grid" x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} />
            <text x={M.l - 8} y={sy(t) + 4} textAnchor="end">
              {pct(t, 0)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={sx(t)} y={H - M.b + 18} textAnchor="middle">
            {dollars(t)}
          </text>
        ))}
        <line className="axis" x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} />
        <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
        <text x={(W + M.l) / 2} y={H - 6} textAnchor="middle">
          dollars per successful trial (lower is better)
        </text>
        <text transform={`translate(14 ${(H - M.b + M.t) / 2}) rotate(-90)`} textAnchor="middle">
          faulted success
        </text>
        <polyline
          points={frontPts.map((p) => `${sx(p.x)},${sy(p.y.value)}`).join(' ')}
          fill="none"
          stroke="#ff5a1a"
          strokeDasharray="4 4"
          strokeOpacity={0.6}
        />
        {pts.map((p) => (
          <g key={p.r.config_id}>
            <line x1={sx(p.x)} x2={sx(p.x)} y1={sy(p.y.lo)} y2={sy(p.y.hi)} stroke={seriesColor(p.i)} strokeOpacity={0.5} />
            <rect
              x={sx(p.x) - 5}
              y={sy(p.y.value) - 5}
              width={10}
              height={10}
              fill={front.has(p.r.config_id) ? seriesColor(p.i) : 'none'}
              stroke={seriesColor(p.i)}
            />
            <text
              className="label"
              x={sx(p.x) > W * 0.8 ? sx(p.x) - 10 : sx(p.x) + 10}
              y={sy(p.y.value) - 8}
              textAnchor={sx(p.x) > W * 0.8 ? 'end' : 'start'}
            >
              {p.r.harness.name}
            </text>
          </g>
        ))}
      </svg>
      <p className="chart-note">Filled squares are on the Pareto front. Vertical lines are 95% intervals.</p>
    </div>
  );
}
