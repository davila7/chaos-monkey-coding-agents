import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { SiteNav } from '@/components/SiteNav';
import { formatDate } from '@/lib/blog';
import { pct, usd } from '@/lib/format';
import { REPO, SPEC } from '@/lib/links';
import { callRange, smokeRuns, totalFaults, type SmokeRun } from '@/lib/smoke';

export const metadata: Metadata = { title: 'Smoke runs | Chaos Monkey for Coding Agents' };

/** SPEC 10.3: a task needs at least this many eligible calls in clean pilot runs. */
const EXPOSURE_FLOOR = 8;
const DECISIONS = `${REPO}/blob/main/DECISIONS.md`;

/** What each run was for. Numbers stay out of these notes; the tables read them from the data. */
const NOTES: Record<string, ReactNode> = {
  '2026-10-11': (
    <>
      Track N, <code>cc-claude</code> only. The tasks of this run were later rebuilt under D-0023, D-0024 and D-0026, so
      its trials sit below the exposure floor of {EXPOSURE_FLOOR} in <a href={`${SPEC}#103-authoring-rules`}>SPEC 10.3</a>{' '}
      and the moderate profile had few eligible calls to fault.
    </>
  ),
  '2026-10-15-track-s': (
    <>
      Track S, <code>fx-claude</code> and <code>cc-claude</code> on three service tasks, one attempt per task and profile (
      <a href={DECISIONS}>D-0030</a>). The tables pool both configs. One attempt per cell supports no comparison between
      them. The cost columns undercount <code>fx-claude</code>: some of its trials have no cost in <code>result.json</code>{' '}
      because the gateway settled them later; the settled costs are in <code>settled-usage.json</code> next to the summary.
    </>
  ),
};

function Run({ run }: { run: SmokeRun }) {
  const { id, date, source, summary } = run;
  const calls = callRange(summary.trials);
  const faults = totalFaults(summary);
  return (
    <section className="block" id={id}>
      <h2>
        <time dateTime={date}>{formatDate(date)}</time>
        {id !== date && <span className="sub">{id.slice(11)}</span>}
      </h2>
      <p className="page-text">
        {summary.trials.length} trials, {faults === 0 ? 'no fault applied' : `${faults} faults applied`}, between{' '}
        {calls.min} and {calls.max} eligible tool calls per trial. {NOTES[id]} Source:{' '}
        <a href={`${REPO}/blob/main/${source}`}>
          <code>{source}</code>
        </a>
        .
      </p>

      <h3>Per profile</h3>
      <div className="table-wrap">
        <table className="compact">
          <thead>
            <tr>
              <th>Profile</th>
              <th className="num">Trials</th>
              <th className="num">pass^1</th>
              <th className="num">Total cost</th>
              <th className="num">Mean cost</th>
              <th className="num">Faults applied</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.profiles).map(([name, p]) => (
              <tr key={name}>
                <td>{name}</td>
                <td className="num">{p.trials}</td>
                <td className="num">{pct(p.pass1)}</td>
                <td className="num">{usd(p.cost_usd_total)}</td>
                <td className="num">{usd(p.cost_usd_mean)}</td>
                <td className="num">{p.faults_applied}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Per trial</h3>
      <div className="table-wrap">
        <table className="compact">
          <thead>
            <tr>
              <th>Task</th>
              <th>Profile</th>
              <th className="num">Reward</th>
              <th className="num">Cost</th>
              <th className="num">Eligible calls</th>
              <th>Completion status</th>
            </tr>
          </thead>
          <tbody>
            {summary.trials.map((t) => (
              <tr key={t.trial}>
                <td>
                  {t.task}
                  <span className="sub">{t.trial}</span>
                </td>
                <td>{t.profile}</td>
                <td className="num">{t.reward === null ? '-' : t.reward.toFixed(2)}</td>
                <td className="num">{t.cost_usd === null ? '-' : usd(t.cost_usd)}</td>
                <td className="num">{t.eligible_calls}</td>
                <td>{t.infra_failure ? `infra failure: ${t.infra_failure}` : (t.status ?? '-')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function Smoke() {
  const runs = smokeRuns();
  return (
    <>
      <SiteNav />
      <main className="wrap page-wrap">
        <div className="notice">
          <strong>Smoke runs, not benchmark results.</strong> These trials check the pipeline. They carry no ranking and
          support no comparison between configs or harnesses.
        </div>
        <h1 className="blog-title">Smoke runs</h1>
        <p className="blog-lede">
          Each run checked the path from a trial to the analysis summary to this page: Harbor ran each trial in a container,
          the injector logged its decisions, and the analysis read the job directories and wrote the summary shown here.
          Newest first.
        </p>
        {runs.map((run) => (
          <Run key={run.id} run={run} />
        ))}
      </main>
      <footer>
        <div className="wrap">
          Every number on this page is read at build time from the <code>summary.json</code> named under each run, copied
          into the site by <code>pnpm sync-data</code>.
        </div>
      </footer>
    </>
  );
}
