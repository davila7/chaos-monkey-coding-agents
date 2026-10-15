import type { Metadata } from 'next';
import { SiteNav } from '@/components/SiteNav';
import { formatDate } from '@/lib/blog';
import { pct, usd } from '@/lib/format';
import { REPO, SPEC } from '@/lib/links';
import { callRange, latestSmokeRun, totalFaults } from '@/lib/smoke';

export const metadata: Metadata = { title: 'Smoke run | Chaos Monkey for Coding Agents' };

/** SPEC 10.3: a task needs at least this many eligible calls in clean pilot runs. */
const EXPOSURE_FLOOR = 8;

export default function Smoke() {
  const { date, source, summary } = latestSmokeRun();
  const calls = callRange(summary.trials);
  const faults = totalFaults(summary);
  const profiles = Object.entries(summary.profiles);
  return (
    <>
      <SiteNav />
      <main className="wrap page-wrap">
        <div className="notice">
          <strong>Smoke run, not a benchmark result.</strong> These trials check the pipeline. They carry no ranking and
          support no comparison between configs or harnesses.
        </div>
        <h1 className="blog-title">Smoke run</h1>
        <p className="blog-lede">
          <time dateTime={date}>{formatDate(date)}</time>, {summary.trials.length} trials. Source:{' '}
          <a href={`${REPO}/blob/main/${source}`}>
            <code>{source}</code>
          </a>
          .
        </p>
        <p className="page-text">
          The run checked the path from a trial to the analysis summary to this page: Harbor ran each trial in a container,
          the injector logged its decisions, and the analysis read the job directories and wrote the summary shown here. It
          did not measure fault recovery. {faults === 0 ? 'No fault was applied.' : `${faults} faults were applied.`} Trials
          made {calls.min === calls.max ? calls.min : `${calls.min} to ${calls.max}`} eligible tool calls, below the
          exposure floor of {EXPOSURE_FLOOR} in <a href={`${SPEC}#103-authoring-rules`}>SPEC 10.3</a>, so the moderate
          profile was expected to apply few or no faults. The tasks were later rebuilt under D-0023, D-0024 and D-0026; the clean
          pilots on the rebuilt tasks are described in the build log.
        </p>

        <section className="block">
          <h2>Per profile</h2>
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
                {profiles.map(([name, p]) => (
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
        </section>

        <section className="block">
          <h2>Per trial</h2>
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
      </main>
      <footer>
        <div className="wrap">
          Every number on this page is read at build time from <code>{source}</code>, copied into the site by{' '}
          <code>pnpm sync-data</code>.
        </div>
      </footer>
    </>
  );
}
