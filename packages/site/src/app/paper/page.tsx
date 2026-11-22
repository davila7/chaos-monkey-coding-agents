import type { Metadata } from 'next';
import { CopyButton } from '@/components/CopyButton';
import { SiteNav } from '@/components/SiteNav';
import { REPO } from '@/lib/links';
import { BIBTEX, DOI_URL, PAPER } from '@/lib/paper';

export const metadata: Metadata = {
  title: 'Paper | Chaos Monkey Coding Agent Benchmark',
  description: PAPER.title,
};

const HF = 'https://huggingface.co/datasets/davila7/chaos-monkey-coding-agents';

export default function PaperPage() {
  return (
    <>
      <SiteNav />
      <main className="wrap paper-wrap">
        <div className="paper-head">
          <a className="paper-cover" href={PAPER.pdf}>
            <img src={PAPER.cover} alt="First page of the paper" width={720} height={932} />
          </a>
          <div>
            <p className="paper-kicker">
              {PAPER.venue} &middot; {PAPER.date}
            </p>
            <h1 className="paper-title">{PAPER.title}</h1>
            <p className="paper-author">
              {PAPER.author} <span>&middot; {PAPER.affiliation}</span>
            </p>
            <div className="cta paper-cta">
              <a className="btn primary" href={PAPER.pdf}>
                PDF &darr;
              </a>
              <a className="btn" href={DOI_URL}>
                DOI {PAPER.doi}
              </a>
              <a className="btn" href={REPO}>
                Code
              </a>
              <a className="btn" href={HF}>
                Data
              </a>
            </div>
          </div>
        </div>

        <section className="block">
          <h2>Abstract</h2>
          <p className="paper-abstract">{PAPER.abstract}</p>
        </section>

        <section className="block" id="cite">
          <h2>Cite</h2>
          <div className="bibtex">
            <CopyButton text={BIBTEX} />
            <pre>{BIBTEX}</pre>
          </div>
          <p className="paper-license">
            Paper license {PAPER.license}. Code Apache-2.0, data CC BY 4.0.
          </p>
        </section>
      </main>
    </>
  );
}
