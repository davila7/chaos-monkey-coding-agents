// The PDF in public/paper is the file of Zenodo record 24403112 (md5 in D-0058); the citation uses the concept DOI so it
// keeps resolving to the latest version, as in CITATION.cff.
export const PAPER = {
  title: 'Chaos Monkey for Coding Agents: Measuring How Coding-Agent Harnesses Recover When Their Tools Fail',
  author: 'Daniel Ávila Arias',
  affiliation: 'Independent Researcher',
  date: 'November 2026',
  venue: 'Preprint, Zenodo',
  license: 'CC BY 4.0',
  doi: '10.5281/zenodo.24403111',
  pdf: '/paper/cmca-paper.pdf',
  cover: '/paper/cmca-paper-page1.png',
  abstract: [
    'Coding agents run inside harnesses that execute their tool calls, and those tools fail: commands error, reads return nothing or stale data, and calls that succeeded report failure.',
    "We present Chaos Monkey for Coding Agents (CMCA), an open benchmark that applies one seeded fault model at two layers: an MCP proxy in front of mock services, and injectors loaded through each harness's own hooks that fault its built-in read, edit, search and shell tools, restricted to fault types a conformance suite shows each harness delivers.",
    'Every configuration uses the same main model, so rows compare harness configurations; the native-track fx row is fxh, a fork that adds tool hooks.',
    'Besides success under faults, CMCA reports whether agents state their outcome honestly, whether stale data reaches their output, and what recovery costs.',
    'On 37 service and 36 native tasks (3,011 trial runs), fx leads the service track (83 of 111 faulted trials) and fxh the native track (95 of 108), but no pairwise difference survives Holm correction.',
    'Among failed trials that received a fault, agents still reported success in 60% to 94% of cases.',
    'Code, tasks, trajectories and analysis are public.',
  ].join(' '),
} as const;

export const DOI_URL = `https://doi.org/${PAPER.doi}`;

// Same entry as README.md.
export const BIBTEX = `@misc{avila_arias_cmca_paper_2026,
  author    = {\\'{A}vila Arias, Daniel},
  title     = {${PAPER.title}},
  year      = {2026},
  publisher = {Zenodo},
  note      = {Preprint},
  doi       = {${PAPER.doi}},
  url       = {${DOI_URL}}
}`;
