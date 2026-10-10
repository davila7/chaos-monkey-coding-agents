'use client';

import { useMemo, useState } from 'react';
import { rankBands } from '@/lib/bands';
import { compact, dollars, halfWidth, pct } from '@/lib/format';
import type { Interval, Row, SiteData } from '@/lib/schema';
import { CurveChart } from './CurveChart';
import { ParetoChart } from './ParetoChart';

type View = 'table' | 'pareto' | 'curves';
type SortKey = 'faulted' | 'clean' | 'rr' | 'pass3' | 'overclaim' | 'poison' | 'cost' | 'tokens';

const SORTERS: Record<SortKey, (r: Row) => number | null> = {
  faulted: (r) => r.metrics.faulted_success.value,
  clean: (r) => r.metrics.clean_pass1.value,
  rr: (r) => r.metrics.rr?.value ?? null,
  pass3: (r) => r.metrics.pass3_moderate?.value ?? null,
  overclaim: (r) => r.metrics.overclaim_rate?.value ?? null,
  poison: (r) => r.metrics.poison_propagation_rate?.value ?? null,
  cost: (r) => r.metrics.dollars_per_success,
  tokens: (r) => r.metrics.tokens_total,
};

/** Lower is better for these, so the first click sorts ascending. */
const ASCENDING_FIRST = new Set<SortKey>(['overclaim', 'poison', 'cost', 'tokens']);

function ScoreCell({ c }: { c: Interval }) {
  return (
    <div className="score">
      <div className="val">
        <b>{pct(c.value)}</b> <span>{halfWidth(c)}%</span>
      </div>
      <div className="bar" aria-hidden="true">
        <div className="fill" style={{ width: `${c.value * 100}%` }} />
        <div className="ci" style={{ left: `${c.lo * 100}%`, width: `${(c.hi - c.lo) * 100}%` }} />
      </div>
    </div>
  );
}

const cell = (c: Interval | null) => (c ? pct(c.value) : '-');

export function Leaderboard({ data }: { data: SiteData }) {
  const [boardId, setBoardId] = useState(data.boards[0]?.id ?? '');
  const [view, setView] = useState<View>('table');
  const [sort, setSort] = useState<{ key: SortKey; asc: boolean }>({ key: 'faulted', asc: false });

  const board = data.boards.find((b) => b.id === boardId) ?? data.boards[0];
  const showBands = data.kind !== 'smoke';

  const rows = useMemo(() => {
    if (!board) return [];
    const bands = rankBands(board.rows.map((r) => r.metrics.faulted_success));
    const withBand = board.rows.map((r, i) => ({ r, band: bands[i]! }));
    const get = SORTERS[sort.key];
    return withBand.sort((a, b) => {
      const x = get(a.r);
      const y = get(b.r);
      if (x === null && y === null) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return sort.asc ? x - y : y - x;
    });
  }, [board, sort]);

  const header = (key: SortKey, label: string, num = true) => (
    <th
      className={`sortable${num ? ' num' : ''}${sort.key === key ? ' active' : ''}`}
      aria-sort={sort.key === key ? (sort.asc ? 'ascending' : 'descending') : 'none'}
      onClick={() =>
        setSort((s) => (s.key === key ? { key, asc: !s.asc } : { key, asc: ASCENDING_FIRST.has(key) }))
      }
    >
      {label}
      <span className="arrow">{sort.key === key ? (sort.asc ? '↑' : '↓') : '⇅'}</span>
    </th>
  );

  return (
    <>
      {data.kind === 'sample' && (
        <div className="notice">
          <strong>Sample data.</strong> Every config and number below is invented to preview the layout. None of it is a
          benchmark result. Production builds read <code>data/results.json</code> instead.
        </div>
      )}
      {data.kind === 'smoke' && (
        <div className="notice">
          <strong>Smoke run, not a benchmark result.</strong> This run checks the pipeline end to end. It carries no
          ranking and supports no comparison between configs.
        </div>
      )}

      <div className="toolbar">
        <div className="seg" role="group" aria-label="Board">
          {data.boards.map((b) => (
            <button key={b.id} aria-pressed={b.id === board?.id} onClick={() => setBoardId(b.id)}>
              {b.title}
            </button>
          ))}
        </div>
        <span className="spacer" />
        {data.release && <span className="sub">release {data.release}</span>}
        <a className="icon-btn" href="/data.json" title="Download JSON" aria-label="Download JSON">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M2.5 13.5h11" />
          </svg>
        </a>
        {board && board.rows.length > 0 && (
        <div className="seg" role="group" aria-label="View">
          {(['table', 'pareto', 'curves'] as View[]).map((v) => (
            <button key={v} aria-pressed={view === v} onClick={() => setView(v)}>
              {v}
            </button>
          ))}
        </div>
        )}
      </div>

      {board && <p className="board-desc">{board.description}</p>}

      {!board || board.rows.length === 0 ? (
        <div className="table-wrap">
          <div className="empty">
            No published results yet.
            <br />
            Rows appear here once <code>cmca analyze</code> writes them from committed job directories.
          </div>
        </div>
      ) : view === 'table' ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {showBands && <th className="num">Band</th>}
                <th>Harness</th>
                <th>Model</th>
                {header('faulted', 'Faulted success', false)}
                {header('clean', 'Clean')}
                {header('rr', 'RR')}
                {header('pass3', 'pass^3')}
                {header('overclaim', 'Overclaim')}
                {header('poison', 'Poison')}
                {header('cost', '$ / success')}
                {header('tokens', 'Tokens')}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ r, band }) => (
                <tr key={r.config_id}>
                  {showBands && <td className="band">{band}</td>}
                  <td>
                    {r.harness.name}
                    <span className="sub">{r.harness.version}</span>
                  </td>
                  <td>
                    {r.model.id}
                    {r.model.reasoning && <span className="sub">({r.model.reasoning})</span>}
                  </td>
                  <td>
                    <ScoreCell c={r.metrics.faulted_success} />
                  </td>
                  <td className="num">{cell(r.metrics.clean_pass1)}</td>
                  <td className="num">{r.metrics.rr ? r.metrics.rr.value.toFixed(2) : '-'}</td>
                  <td className="num">{cell(r.metrics.pass3_moderate)}</td>
                  <td className="num">{cell(r.metrics.overclaim_rate)}</td>
                  <td className="num">{cell(r.metrics.poison_propagation_rate)}</td>
                  <td className="num">{r.metrics.dollars_per_success === null ? '-' : dollars(r.metrics.dollars_per_success)}</td>
                  <td className="num">{r.metrics.tokens_total === null ? '-' : compact(r.metrics.tokens_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : view === 'pareto' ? (
        <ParetoChart rows={board.rows} />
      ) : (
        <CurveChart rows={board.rows} />
      )}
    </>
  );
}
