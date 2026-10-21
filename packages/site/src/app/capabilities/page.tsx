import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { SiteNav } from '@/components/SiteNav';
import { type Cell, grid, loadCapabilities } from '@/lib/capabilities';
import { REPO, SPEC } from '@/lib/links';

export const metadata: Metadata = { title: 'Capabilities | Chaos Monkey for Coding Agents' };

const CRASH: Record<string, string> = {
  fail_open: 'fail open: with an injector build that throws on load, the probe shell call returned its real output',
  fail_closed: 'fail closed: with an injector build that throws on load, the probe shell call did not return its real output',
};

// fxh is CMCA's fork of fx (D-0040) and was probed with a stub model, unlike the other harnesses.
const NOTE: Record<string, ReactNode> = {
  fxh: (
    <>
      fxh is a fork of fx 0.0.13 with tool hooks (<a href="https://github.com/davila7/fxh">davila7/fxh</a>, D-0040). Its
      probes ran against a stub model, not a live one (<a href={`${REPO}/blob/main/docs/verification/V-27.md`}>V-27</a>).
    </>
  ),
};

const LABEL: Record<Cell['state'], string> = {
  delivered: 'delivered',
  gap: 'gap',
  failed: 'failed',
  not_tested: 'not tested',
  'n/a': 'n/a',
};

function CellView({ c }: { c: Cell }) {
  const runs = c.state === 'delivered' || c.state === 'gap' || c.state === 'failed' ? ` ${c.runs_passed}/${c.runs}` : '';
  return (
    <td className={`cap cap-${c.state.replace('/', '')}`} title={c.reason}>
      {LABEL[c.state]}
      {runs && <span className="sub">{runs}</span>}
    </td>
  );
}

export default function CapabilitiesPage() {
  const caps = loadCapabilities();
  return (
    <>
      <SiteNav />
      <main className="wrap page-wrap">
        <h1 className="blog-title">Capabilities</h1>
        <p className="blog-lede">
          What the conformance suite (<a href={`${SPEC}#96-conformance-suite`}>SPEC 9.6</a>, D-0020) observed for each
          pinned harness version. Each cell is one fault type on one capability class, probed 3 times. A fault type enters
          the parity set when every class the harness exposes passes every run, except classes recorded as parity gaps.
        </p>
        <div className="grid-defs legend-defs">
          <div>
            <b className="cap-delivered">delivered</b>
            <p>The payload reached the model and the side-effect check held in every run.</p>
          </div>
          <div>
            <b className="cap-gap">gap</b>
            <p>A reviewed parity gap: the harness does not deliver this type on this class. The reason is listed below.</p>
          </div>
          <div>
            <b className="cap-not_tested">not tested</b>
            <p>No tool on the harness maps to the class, so conformance skipped it.</p>
          </div>
          <div>
            <b className="cap-na">n/a</b>
            <p>No harness has this type on this class: the fault catalog does not apply it there.</p>
          </div>
        </div>

        {caps.map((c) => {
          const g = grid(caps, c);
          const file = `capabilities/${c.harness}@${c.version}.json`;
          return (
            <section key={file} id={c.harness} className="block">
              <h2>
                {c.harness} {c.version}
              </h2>
              {NOTE[c.harness] && <p className="page-text">{NOTE[c.harness]}</p>}
              <div className="grid-defs">
                <div>
                  <b>Crash behavior</b>
                  <p>{CRASH[c.crash_behavior]}</p>
                </div>
                <div>
                  <b>Injector p95 latency</b>
                  <p>{c.injector_p95_ms} ms</p>
                </div>
                <div>
                  <b>Parity set</b>
                  <p>{c.parity_set.length ? c.parity_set.join(', ') : 'empty'}</p>
                </div>
                <div>
                  <b>Tool map</b>
                  <p>
                    {Object.entries(c.tool_map)
                      .map(([tool, cls]) => `${tool} → ${cls}`)
                      .join(', ')}
                  </p>
                </div>
              </div>
              <div className="table-wrap cap-table">
                <table className="compact">
                  <thead>
                    <tr>
                      <th>Type</th>
                      {g.classes.map((k) => (
                        <th key={k}>{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {g.types.map((t, i) => (
                      <tr key={t}>
                        <td>
                          {t}
                          {!c.parity_set.includes(t) && <span className="sub">not in parity set</span>}
                        </td>
                        {g.cells[i]!.map((cell, j) => (
                          <CellView key={g.classes[j]} c={cell} />
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 className="cap-sub">Parity gaps</h3>
              {c.parity_gaps.length === 0 ? (
                <p className="page-text">None recorded.</p>
              ) : (
                <ul className="page-text">
                  {c.parity_gaps.map((p) => (
                    <li key={`${p.type}:${p.capability}`}>
                      <code>
                        {p.type} on {p.capability}
                      </code>
                      : {p.reason}
                    </li>
                  ))}
                </ul>
              )}
              <p className="chart-note">
                Generated {c.generated_at}. Source:{' '}
                <a href={`${REPO}/blob/main/${file}`}>
                  <code>{file}</code>
                </a>
              </p>
            </section>
          );
        })}
      </main>
      <footer>
        <div className="wrap">
          Every value on this page is read at build time from <code>capabilities/*.json</code>, copied into the site by{' '}
          <code>pnpm sync-data</code>.
        </div>
      </footer>
    </>
  );
}
