import { pct } from '@/lib/format';
import type { Row } from '@/lib/schema';
import { seriesColor } from './palette';

const W = 960;
const H = 420;
const M = { l: 56, r: 24, t: 20, b: 44 };

export function CurveChart({ rows }: { rows: Row[] }) {
  const series = rows.map((r, i) => ({ r, i, pts: r.curve ?? [] })).filter((s) => s.pts.length > 0);
  if (series.length === 0) return <div className="chart empty">No degradation curve data for this board.</div>;

  const rates = [...new Set(series.flatMap((s) => s.pts.map((p) => p.base_rate)))].sort((a, b) => a - b);
  const xMax = rates[rates.length - 1] || 1;
  const sx = (v: number) => M.l + (v / xMax) * (W - M.l - M.r);
  const sy = (v: number) => H - M.b - v * (H - M.t - M.b);
  const profileAt = new Map(series.flatMap((s) => s.pts.map((p) => [p.base_rate, p.profile] as const)));

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="pass^1 versus fault base rate">
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
          <g key={t}>
            <line className="grid" x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} />
            <text x={M.l - 8} y={sy(t) + 4} textAnchor="end">
              {pct(t, 0)}
            </text>
          </g>
        ))}
        {rates.map((r, k) => (
          <text key={r} x={sx(r)} y={H - M.b + 18} textAnchor={k === 0 ? 'start' : k === rates.length - 1 ? 'end' : 'middle'}>
            {profileAt.get(r)} {pct(r, 0)}
          </text>
        ))}
        <line className="axis" x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} />
        <line className="axis" x1={M.l} x2={M.l} y1={M.t} y2={H - M.b} />
        <text transform={`translate(14 ${(H - M.b + M.t) / 2}) rotate(-90)`} textAnchor="middle">
          pass^1
        </text>
        {series.map(({ r, i, pts }) => {
          const sorted = [...pts].sort((a, b) => a.base_rate - b.base_rate);
          const c = seriesColor(i);
          const band = [
            ...sorted.map((p) => `${sx(p.base_rate)},${sy(p.pass1.hi)}`),
            ...[...sorted].reverse().map((p) => `${sx(p.base_rate)},${sy(p.pass1.lo)}`),
          ].join(' ');
          return (
            <g key={r.config_id}>
              <polygon points={band} fill={c} fillOpacity={0.07} />
              <polyline
                points={sorted.map((p) => `${sx(p.base_rate)},${sy(p.pass1.value)}`).join(' ')}
                fill="none"
                stroke={c}
                strokeWidth={2}
              />
              {sorted.map((p) => (
                <rect key={p.base_rate} x={sx(p.base_rate) - 3} y={sy(p.pass1.value) - 3} width={6} height={6} fill={c} />
              ))}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {series.map(({ r, i }) => (
          <span key={r.config_id}>
            <i style={{ background: seriesColor(i) }} />
            {r.harness.name} / {r.model.id}
          </span>
        ))}
      </div>
      <p className="chart-note">Shaded areas are 95% intervals. Base rate is the share of eligible tool calls that fail.</p>
    </div>
  );
}
