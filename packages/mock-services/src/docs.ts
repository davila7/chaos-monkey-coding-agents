import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { BadRequest, guarded, NotFound, page } from './common.js';
import type { Service } from './server.js';

export const DOCS_PAGE_SIZE = 5;
const SNIPPET = 160;

const Doc = z
  .object({
    id: z.string(),
    title: z.string(),
    tags: z.array(z.string()),
    updated_at: z.string(),
    body: z.string(),
  })
  .strict();

export const DocsFixtureSchema = z.object({ schema: z.literal('docs-fixture/1'), docs: z.array(Doc) }).strict();

export type Doc = z.infer<typeof Doc>;
export type DocsFixture = z.infer<typeof DocsFixtureSchema>;

/** Read-only document store. Ranking is by matched term count, then id, so results never depend on load order. */
export class DocsStore {
  private readonly docs = new Map<string, Doc>();

  constructor(fixture: DocsFixture) {
    for (const d of DocsFixtureSchema.parse(fixture).docs) {
      if (this.docs.has(d.id)) throw new Error(`duplicate doc id ${d.id}`);
      this.docs.set(d.id, structuredClone(d));
    }
  }

  search(a: { query: string; tag?: string | undefined; page?: number | undefined }) {
    const terms = a.query.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) throw new BadRequest('400 Bad Request: query must contain a word');
    const hits = [...this.docs.values()]
      .filter((d) => a.tag === undefined || d.tags.includes(a.tag))
      .map((d) => {
        const text = `${d.title}\n${d.body}`.toLowerCase();
        return { d, score: terms.filter((t) => text.includes(t)).length };
      })
      .filter((h) => h.score > 0)
      .sort((x, y) => y.score - x.score || (x.d.id < y.d.id ? -1 : 1));
    const p = page(hits, a.page, DOCS_PAGE_SIZE);
    return {
      ...p,
      results: p.results.map(({ d, score }) => ({ id: d.id, title: d.title, tags: d.tags, updated_at: d.updated_at, matched_terms: score, snippet: snippet(d.body, terms) })),
    };
  }

  doc(id: string): Doc {
    const d = this.docs.get(id);
    if (!d) throw new NotFound(`404 Not Found: doc ${id} does not exist`);
    return structuredClone(d);
  }

  snapshot() {
    return { schema: 'docs-state/1' as const, mutations: [] };
  }
}

/** The first body line that contains a query term, cut to SNIPPET characters. */
function snippet(body: string, terms: string[]): string {
  const lines = body.split('\n').filter((l) => l.trim() !== '');
  const line = lines.find((l) => terms.some((t) => l.toLowerCase().includes(t))) ?? lines[0] ?? '';
  return line.length > SNIPPET ? `${line.slice(0, SNIPPET - 3)}...` : line;
}

export function docsService(store: DocsStore): Service {
  return {
    name: 'docs',
    version: '3.1.0',
    snapshot: () => store.snapshot(),
    register(s: McpServer) {
      s.registerTool(
        'search_docs',
        {
          description: `Search internal documentation. A doc matches when its title or body contains any query word; results with more matched words come first, ${DOCS_PAGE_SIZE} per page. Follow next_page until it is null.`,
          inputSchema: {
            query: z.string().min(1),
            tag: z.string().optional(),
            page: z.number().int().min(1).optional().describe('1-based page number'),
          },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.search(a)),
      );
      s.registerTool(
        'get_doc',
        {
          description: 'Get the full text of one doc by id.',
          inputSchema: { id: z.string().min(1) },
          annotations: { readOnlyHint: true },
        },
        async (a) => guarded(() => store.doc(a.id)),
      );
    },
  };
}
