import { dollars } from '@/lib/format';
import type { HeadlineRow } from '@/lib/headline';

const whole = (v: number) => `${Math.round(v * 100)}%`;

export function HomeChart({ rows }: { rows: HeadlineRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="home-chart" role="table" aria-label="Tasks finished with tool failures injected">
      <div className="hc-row hc-head" role="row">
        <span role="columnheader">Rank</span>
        <span role="columnheader">Agent</span>
        <span role="columnheader">Tasks finished</span>
        <span role="columnheader" />
        <span role="columnheader" className="hc-count">Finished / sent</span>
      </div>
      {rows.map((r) => (
        // tabIndex makes the tooltip reachable by keyboard and by tap on touch screens.
        <div key={r.harness} className={r.rank === 1 ? 'hc-row hc-win' : 'hc-row'} role="row" tabIndex={0}>
          <span className="hc-rank" role="cell">#{r.rank}</span>
          <span className="hc-name" role="cell">{r.harness}</span>
          <span className="hc-track" role="cell" aria-hidden="true">
            <span className="hc-bar" style={{ width: `${r.share * 100}%` }} />
          </span>
          <span className="hc-pct" role="cell">{whole(r.share)}</span>
          <span className="hc-count" role="cell">
            {r.succeeded} / {r.sent}
          </span>
          <span className="hc-tip" role="tooltip">
            <b>
              {r.harness} {r.version}
            </b>
            <span>
              Model: {r.model}
              {r.reasoning ? ` (${r.reasoning})` : ''}
            </span>
            <span>
              With tool failures: {r.succeeded} of {r.sent} finished ({whole(r.share)})
            </span>
            <span>Without failures: {whole(r.clean)} finished</span>
            {r.dollarsPerSuccess !== null ? <span>Cost per finished task: {dollars(r.dollarsPerSuccess)}</span> : null}
          </span>
        </div>
      ))}
    </div>
  );
}
