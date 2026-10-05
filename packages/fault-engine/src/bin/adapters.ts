import { FAULT_PHASE, type FaultDecision, type FaultType } from '../types.js';

export interface DecideRequest {
  toolName: string;
  capability: string;
  args: unknown;
  paths?: string[];
  agentId?: string;
}

/**
 * What a post-phase output transform needs from the decision. Returned by
 * the decide step and handed back unchanged to `tt-decide --apply`, so the
 * transform runs in the same engine code without touching trial state.
 */
export interface PostRef {
  type: FaultType;
  payload_id: string;
  poison_index?: number;
  drift_index?: number;
}

export function postRef(d: FaultDecision): PostRef | null {
  if (!d.inject || !d.type || !d.payloadId || FAULT_PHASE[d.type] !== 'post') return null;
  return {
    type: d.type,
    payload_id: d.payloadId,
    ...(d.poisonIndex !== undefined ? { poison_index: d.poisonIndex } : {}),
    ...(d.driftIndex !== undefined ? { drift_index: d.driftIndex } : {}),
  };
}

export function fromPostRef(ref: PostRef): FaultDecision {
  return {
    inject: true,
    type: ref.type,
    payloadId: ref.payload_id,
    key: '',
    occurrence: 0,
    seq: -1,
    ...(ref.poison_index !== undefined ? { poisonIndex: ref.poison_index } : {}),
    ...(ref.drift_index !== undefined ? { driftIndex: ref.drift_index } : {}),
  };
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
    const post = postRef(d);
    return JSON.stringify({
      apply: true,
      type: d.type,
      phase: d.type ? FAULT_PHASE[d.type] : 'pre',
      payload_id: d.payloadId,
      text: r.text,
      ...(d.delayMs !== undefined ? { delay_ms: d.delayMs } : {}),
      ...(post ? { post } : {}),
    });
  },
};

export const adapters: Record<string, StdioAdapter> = { generic };
