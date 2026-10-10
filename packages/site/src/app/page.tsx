import { Leaderboard } from '@/components/Leaderboard';
import { SiteNav } from '@/components/SiteNav';
import { loadSiteData } from '@/lib/data';
import { REPO, SPEC } from '@/lib/links';

const METRICS: [string, string][] = [
  ['Faulted Success', 'pass^1 under the moderate profile (15% of eligible tool calls fail, at most 6 per trial). The headline and the default sort.'],
  ['Clean', 'pass^1 with no faults. The baseline each config is compared against.'],
  ['RR', 'Robustness Retention: Faulted Success divided by Clean, over tasks the config solves without faults. Never the primary sort.'],
  ['pass^3', 'Probability that 3 attempts on the same task all succeed under moderate faults (unbiased estimator, n = 5).'],
  ['Overclaim', 'Among failed faulted trials, the share where the agent reported success anyway.'],
  ['Poison', 'Share of plausible-but-wrong outputs whose marker token ends up in the final artifacts.'],
  ['$ / success', 'Model spend divided by successful trials under moderate faults.'],
  ['Band', 'Configs whose 95% intervals for Faulted Success overlap share a band. Bands replace ordinal ranks.'],
];

export default function Home() {
  const data = loadSiteData();
  return (
    <>
      <SiteNav />

      <main className="wrap">
        <header className="hero">
          <img className="banner" src="/banner.png" alt="Chaos Monkey: Coding Agent Benchmark" width={2172} height={724} />
          <p className="lede">
            Seeded tool-call failures injected into unmodified coding-agent harnesses. Which harness still finishes the task,
            what recovery costs, and whether it reports the outcome honestly.
          </p>
          <div className="cta">
            <a className="btn primary" href={SPEC}>
              Read the spec &gt;_
            </a>
            <a className="btn" href={REPO}>
              View the code &rarr;
            </a>
          </div>
        </header>

        <section id="results" className="block">
          <Leaderboard data={data} />
        </section>

        <section id="metrics" className="block">
          <h2>Metrics</h2>
          <div className="grid-defs">
            {METRICS.map(([k, v]) => (
              <div key={k}>
                <b>{k}</b>
                <p>{v}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer>
        <div className="wrap">
          Every number on this page comes from a committed analysis artifact
          {data.source ? (
            <>
              {' '}(<code>{data.source}</code>)
            </>
          ) : null}
          . Intervals are 95% hierarchical bootstrap intervals over tasks and attempts.{' '}
          <a href="/data.json">Download the data</a>. Code Apache-2.0, task data CC BY 4.0.
        </div>
      </footer>
    </>
  );
}
