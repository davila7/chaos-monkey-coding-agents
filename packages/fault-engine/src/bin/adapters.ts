import type { FaultDecision } from '../types.js';

export interface DecideRequest {
  toolName: string;
  capability: string;
  args: unknown;
  paths?: string[];
  agentId?: string;
}

export interface DecideResult {
  decision: FaultDecision;
  text: string;
}

/**
 * Maps a harness payload on stdin to a request, and a decision to the
 * harness response on stdout. `respond(null)` must always produce a
 * pass-through response. Harness formats are added once their contract is
 * verified (SPEC 21: V-02, V-03, V-04).
 */
export interface StdioAdapter {
  parse(stdin: string): DecideRequest | null;
  respond(result: DecideResult | null): string;
}

const generic: StdioAdapter = {
  parse(stdin) {
    const p = JSON.parse(stdin) as Record<string, unknown>;
    if (typeof p.tool_name !== 'string' || typeof p.capability !== 'string') return null;
    const req: DecideRequest = { toolName: p.tool_name, capability: p.capability, args: p.args ?? null };
    if (Array.isArray(p.paths)) req.paths = p.paths.filter((x): x is string => typeof x === 'string');
    if (typeof p.agent_id === 'string') req.agentId = p.agent_id;
    return req;
  },
  respond(r) {
    if (!r || !r.decision.inject) return JSON.stringify({ apply: false });
    const d = r.decision;
    return JSON.stringify({
      apply: true,
      type: d.type,
      payload_id: d.payloadId,
      text: r.text,
      ...(d.delayMs !== undefined ? { delay_ms: d.delayMs } : {}),
    });
  },
};

export const adapters: Record<string, StdioAdapter> = { generic };
