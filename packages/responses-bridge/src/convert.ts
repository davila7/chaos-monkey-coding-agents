import type Anthropic from '@anthropic-ai/sdk';

// The parts of a Responses API request that Codex sends (observed with
// Codex 0.163.0, docs/verification/V-28.md). Fields the Messages API has no
// counterpart for (store, include, prompt_cache_key, client_metadata, text)
// are ignored.
export interface ResponsesRequest {
  model: string;
  instructions?: string;
  input: InputItem[];
  tools?: ResponsesTool[];
  tool_choice?: unknown;
  parallel_tool_calls?: boolean;
  reasoning?: { effort?: string | null; summary?: string | null } | null;
  max_output_tokens?: number | null;
}

type Part = { type: string; text?: string; image_url?: string };

export type InputItem =
  | { type: 'message'; role: 'user' | 'assistant' | 'developer' | 'system'; content: string | Part[] }
  | { type: 'reasoning'; id?: string; summary?: { type: string; text: string }[]; encrypted_content?: string | null }
  | { type: 'function_call'; call_id: string; name: string; arguments: string }
  | { type: 'custom_tool_call'; call_id: string; name: string; input: string }
  | { type: 'function_call_output' | 'custom_tool_call_output'; call_id: string; output: string | Part[] }
  | { type: string; [k: string]: unknown };

export type ResponsesTool =
  | { type: 'function'; name: string; description?: string; parameters?: Record<string, unknown> | null }
  | { type: 'custom'; name: string; description?: string; format?: { type: string; syntax?: string; definition?: string } }
  | { type: string; name?: string; [k: string]: unknown };

export type OutputItem =
  | { type: 'message'; id: string; role: 'assistant'; status: 'completed'; content: { type: 'output_text'; text: string; annotations: [] }[] }
  | { type: 'reasoning'; id: string; summary: { type: 'summary_text'; text: string }[]; encrypted_content: string }
  | { type: 'function_call'; id: string; call_id: string; name: string; arguments: string; status: 'completed' }
  | { type: 'custom_tool_call'; id: string; call_id: string; name: string; input: string; status: 'completed' };

export interface Options {
  /** max_tokens when the request does not set max_output_tokens. */
  maxTokens: number;
}

/** Name of the single string field a freeform tool takes as a Messages API tool. */
export const FREEFORM_FIELD = 'input';

const FREEFORM_SENTENCE = /\s*This is a FREEFORM tool, so do not wrap the patch in JSON\./;

/**
 * Anthropic tool names allow `[a-zA-Z0-9_-]{1,128}`. Codex names its tools
 * inside that set (`exec_command`, `mcp__<server>__<tool>`), so the map is
 * identity for every observed name; anything else is rewritten and mapped
 * back on the way out.
 */
export class ToolNames {
  private toWire = new Map<string, string>();
  private fromWire = new Map<string, string>();
  private freeform = new Set<string>();

  markFreeform(name: string): void {
    this.freeform.add(name);
  }

  isFreeform(name: string): boolean {
    return this.freeform.has(name);
  }

  wire(name: string): string {
    const known = this.toWire.get(name);
    if (known) return known;
    let w = name.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 128) || 'tool';
    for (let i = 2; this.fromWire.has(w) && this.fromWire.get(w) !== name; i++) w = `${w.slice(0, 120)}_${i}`;
    this.toWire.set(name, w);
    this.fromWire.set(w, name);
    return w;
  }

  original(wire: string): string {
    return this.fromWire.get(wire) ?? wire;
  }
}

function partsText(content: string | Part[]): string {
  if (typeof content === 'string') return content;
  return content
    .filter((p) => typeof p.text === 'string')
    .map((p) => p.text)
    .join('\n');
}

const DATA_URL = /^data:(image\/(?:png|jpeg|gif|webp));base64,(.*)$/s;

function userBlocks(content: string | Part[]): Anthropic.ContentBlockParam[] {
  if (typeof content === 'string') return content === '' ? [] : [{ type: 'text', text: content }];
  const out: Anthropic.ContentBlockParam[] = [];
  for (const p of content) {
    if (typeof p.text === 'string' && p.text !== '') out.push({ type: 'text', text: p.text });
    else if (p.type === 'input_image' && typeof p.image_url === 'string') {
      const m = DATA_URL.exec(p.image_url);
      if (m) {
        out.push({
          type: 'image',
          source: { type: 'base64', media_type: m[1] as 'image/png', data: m[2]! },
        });
      }
    }
  }
  return out;
}

function toolResultContent(output: string | Part[]): Anthropic.ToolResultBlockParam['content'] {
  if (typeof output === 'string') return output;
  const blocks = userBlocks(output) as (Anthropic.TextBlockParam | Anthropic.ImageBlockParam)[];
  return blocks.length > 0 ? blocks : '';
}

/**
 * Thinking blocks travel through Codex inside a reasoning item's
 * `encrypted_content`, which Codex sends back unchanged on the next request
 * (it asks for `reasoning.encrypted_content` and runs with `store: false`).
 * The Messages API needs them back unchanged in the assistant turn.
 */
export function encodeThinking(block: Anthropic.ThinkingBlock | Anthropic.RedactedThinkingBlock): string {
  const raw =
    block.type === 'thinking'
      ? { type: 'thinking', thinking: block.thinking, signature: block.signature }
      : { type: 'redacted_thinking', data: block.data };
  return Buffer.from(JSON.stringify(raw), 'utf8').toString('base64');
}

function decodeThinking(encoded: string | null | undefined): Anthropic.ContentBlockParam | null {
  if (!encoded) return null;
  try {
    const b = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8')) as Record<string, unknown>;
    if (b.type === 'thinking' && typeof b.thinking === 'string' && typeof b.signature === 'string') {
      return { type: 'thinking', thinking: b.thinking, signature: b.signature };
    }
    if (b.type === 'redacted_thinking' && typeof b.data === 'string') return { type: 'redacted_thinking', data: b.data };
  } catch {
    // Not one of ours (for example a session started against another provider).
  }
  return null;
}

function parseArgs(args: string): Record<string, unknown> {
  try {
    const v = JSON.parse(args) as unknown;
    return v !== null && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export function convertTools(tools: ResponsesTool[] | undefined, names: ToolNames): Anthropic.Tool[] {
  const out: Anthropic.Tool[] = [];
  for (const t of tools ?? []) {
    if (t.type === 'function' && typeof t.name === 'string') {
      const f = t as Extract<ResponsesTool, { type: 'function' }>;
      out.push({
        name: names.wire(f.name),
        description: f.description ?? '',
        input_schema: (f.parameters ?? { type: 'object', properties: {} }) as Anthropic.Tool.InputSchema,
      });
    } else if (t.type === 'custom' && typeof t.name === 'string') {
      // A freeform tool takes raw text; the Messages API has no such tool, so
      // the text goes in one string field and the grammar into the description.
      const c = t as Extract<ResponsesTool, { type: 'custom' }>;
      names.markFreeform(c.name);
      const grammar = c.format?.definition
        ? `\n\nThe \`${FREEFORM_FIELD}\` field holds the raw text, which must follow this ${c.format.syntax ?? ''} grammar:\n${c.format.definition}`
        : '';
      out.push({
        name: names.wire(c.name),
        description: (c.description ?? '').replace(FREEFORM_SENTENCE, '') + grammar,
        input_schema: {
          type: 'object',
          properties: { [FREEFORM_FIELD]: { type: 'string' } },
          required: [FREEFORM_FIELD],
        },
      });
    }
    // Hosted tools (web_search) and namespaces are not sent: the CMCA config
    // disables both (D-0044 progress), and the Messages API cannot run them.
  }
  return out;
}

/**
 * Responses input items to Messages API system and messages. Leading
 * developer and system messages become the system prompt; later ones become
 * user text at their place in the history. Consecutive items of one role
 * merge into one message, and inside a user message tool results come first,
 * as the Messages API requires after a tool call.
 */
export function convertInput(
  req: Pick<ResponsesRequest, 'instructions' | 'input'>,
  names: ToolNames,
): { system: Anthropic.TextBlockParam[]; messages: Anthropic.MessageParam[] } {
  const system: Anthropic.TextBlockParam[] = [];
  if (req.instructions) system.push({ type: 'text', text: req.instructions });
  const messages: Anthropic.MessageParam[] = [];
  let leading = true;

  const push = (role: 'user' | 'assistant', blocks: Anthropic.ContentBlockParam[]) => {
    if (blocks.length === 0) return;
    const last = messages.at(-1);
    if (last && last.role === role) (last.content as Anthropic.ContentBlockParam[]).push(...blocks);
    else messages.push({ role, content: [...blocks] });
  };

  for (const item of req.input) {
    if (item.type === 'message') {
      const m = item as Extract<InputItem, { type: 'message' }>;
      if (m.role === 'developer' || m.role === 'system') {
        const text = partsText(m.content);
        if (text === '') continue;
        if (leading) system.push({ type: 'text', text });
        else push('user', [{ type: 'text', text }]);
        continue;
      }
      leading = false;
      if (m.role === 'assistant') {
        const text = partsText(m.content);
        if (text !== '') push('assistant', [{ type: 'text', text }]);
      } else push('user', userBlocks(m.content));
      continue;
    }
    leading = false;
    if (item.type === 'reasoning') {
      const b = decodeThinking((item as Extract<InputItem, { type: 'reasoning' }>).encrypted_content);
      if (b) push('assistant', [b]);
    } else if (item.type === 'function_call') {
      const f = item as Extract<InputItem, { type: 'function_call' }>;
      push('assistant', [{ type: 'tool_use', id: f.call_id, name: names.wire(f.name), input: parseArgs(f.arguments) }]);
    } else if (item.type === 'custom_tool_call') {
      const c = item as Extract<InputItem, { type: 'custom_tool_call' }>;
      push('assistant', [{ type: 'tool_use', id: c.call_id, name: names.wire(c.name), input: { [FREEFORM_FIELD]: c.input } }]);
    } else if (item.type === 'function_call_output' || item.type === 'custom_tool_call_output') {
      const o = item as { call_id: string; output: string | Part[] };
      push('user', [{ type: 'tool_result', tool_use_id: o.call_id, content: toolResultContent(o.output) }]);
    }
  }

  for (const m of messages) {
    if (m.role !== 'user') continue;
    const blocks = m.content as Anthropic.ContentBlockParam[];
    const results = blocks.filter((b) => b.type === 'tool_result');
    if (results.length > 0 && results.length < blocks.length) {
      m.content = [...results, ...blocks.filter((b) => b.type !== 'tool_result')];
    }
  }
  return { system, messages };
}

const EFFORTS = new Set(['low', 'medium', 'high', 'xhigh', 'max']);

export function convertRequest(req: ResponsesRequest, names: ToolNames, opts: Options): Anthropic.MessageCreateParamsNonStreaming {
  const { system, messages } = convertInput(req, names);
  const tools = convertTools(req.tools, names);
  const effort = req.reasoning?.effort;
  const params: Anthropic.MessageCreateParamsNonStreaming = {
    model: req.model,
    max_tokens: req.max_output_tokens ?? opts.maxTokens,
    // Automatic caching puts the breakpoint on the last block, so each request
    // reads the prefix the previous one wrote, as the other Claude configs do.
    cache_control: { type: 'ephemeral' },
    thinking: { type: 'adaptive' },
    messages,
  };
  if (system.length > 0) params.system = system;
  if (tools.length > 0) {
    params.tools = tools;
    params.tool_choice = req.parallel_tool_calls === false ? { type: 'auto', disable_parallel_tool_use: true } : { type: 'auto' };
  }
  if (effort && EFFORTS.has(effort)) params.output_config = { effort: effort as 'medium' };
  return params;
}

export interface ResponsesUsage {
  input_tokens: number;
  input_tokens_details: { cached_tokens: number };
  output_tokens: number;
  output_tokens_details: { reasoning_tokens: number };
  total_tokens: number;
}

export function convertUsage(u: Anthropic.Usage): ResponsesUsage {
  const read = u.cache_read_input_tokens ?? 0;
  const input = u.input_tokens + read + (u.cache_creation_input_tokens ?? 0);
  return {
    input_tokens: input,
    input_tokens_details: { cached_tokens: read },
    output_tokens: u.output_tokens,
    output_tokens_details: { reasoning_tokens: 0 },
    total_tokens: input + u.output_tokens,
  };
}

/** Messages API content to Responses output items, in order. */
export function convertOutput(msg: Pick<Anthropic.Message, 'id' | 'content'>, names: ToolNames): OutputItem[] {
  const items: OutputItem[] = [];
  msg.content.forEach((b, i) => {
    const id = `${msg.id}_${i}`;
    if (b.type === 'thinking' || b.type === 'redacted_thinking') {
      const text = b.type === 'thinking' ? b.thinking : '';
      items.push({
        type: 'reasoning',
        id: `rs_${id}`,
        summary: text ? [{ type: 'summary_text', text }] : [],
        encrypted_content: encodeThinking(b),
      });
    } else if (b.type === 'text') {
      items.push({
        type: 'message',
        id: `msg_${id}`,
        role: 'assistant',
        status: 'completed',
        content: [{ type: 'output_text', text: b.text, annotations: [] }],
      });
    } else if (b.type === 'tool_use') {
      const input = (b.input ?? {}) as Record<string, unknown>;
      const name = names.original(b.name);
      if (names.isFreeform(name)) {
        // A call without the string field reaches the tool as JSON text, which
        // its parser rejects the way it rejects any malformed input.
        const raw = input[FREEFORM_FIELD];
        const text = typeof raw === 'string' ? raw : JSON.stringify(input);
        items.push({ type: 'custom_tool_call', id: `ctc_${id}`, call_id: b.id, name, input: text, status: 'completed' });
      } else {
        items.push({ type: 'function_call', id: `fc_${id}`, call_id: b.id, name, arguments: JSON.stringify(input), status: 'completed' });
      }
    }
  });
  return items;
}
