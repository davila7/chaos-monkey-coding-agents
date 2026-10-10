import { Leaderboard } from '@/components/Leaderboard';
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
      <nav className="nav">
        <div className="wrap">
          <a className="brand" href="/">
            <img src="/mark.png" alt="" />
            CHAOS MONKEY
          </a>
          <div className="nav-links">
            <a href="#results">Results</a>
            <a href="#metrics">Metrics</a>
            <a href={SPEC}>Spec</a>
          </div>
          <a className="nav-gh" href={REPO} aria-label="GitHub repository">
            <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
          </a>
        </div>
      </nav>

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
