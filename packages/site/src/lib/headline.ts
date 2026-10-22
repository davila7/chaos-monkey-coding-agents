import type { Row, SiteData } from './schema';

/** The home chart reads the one board every harness is on (SPEC 6.4: Track S). */
export const HEADLINE_BOARD = 'track-s';

export type HeadlineRow = {
  rank: number;
  harness: string;
  version: string;
  model: string;
  reasoning: string | null;
  succeeded: number;
  sent: number;
  share: number;
  /** pass^1 with no faults, for the tooltip. */
  clean: number;
  dollarsPerSuccess: number | null;
};

/** Rows with raw counts, best first; equal shares get the same rank (1, 1, 3, ...). */
export function headlineRanking(data: SiteData): HeadlineRow[] {
  const board = data.boards.find((b) => b.id === HEADLINE_BOARD);
  if (!board) return [];
  const rows = board.rows
    .filter((r): r is Row & { faulted_counts: NonNullable<Row['faulted_counts']> } => r.faulted_counts !== null)
    .map((r) => ({
      harness: r.harness.name,
      version: r.harness.version,
      model: r.model.id,
      reasoning: r.model.reasoning,
      clean: r.metrics.clean_pass1.value,
      dollarsPerSuccess: r.metrics.dollars_per_success,
      succeeded: r.faulted_counts.succeeded,
      sent: r.faulted_counts.sent,
      share: r.faulted_counts.succeeded / r.faulted_counts.sent,
    }))
    .sort((a, b) => b.share - a.share || a.harness.localeCompare(b.harness));
  return rows.map((r) => ({ ...r, rank: 1 + rows.filter((o) => o.share > r.share).length }));
}
