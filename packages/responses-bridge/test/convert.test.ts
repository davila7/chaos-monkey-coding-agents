import type Anthropic from '@anthropic-ai/sdk';
import { describe, expect, it } from 'vitest';
import {
  convertInput,
  convertOutput,
  convertRequest,
  convertTools,
  convertUsage,
  encodeThinking,
  ToolNames,
  type ResponsesRequest,
} from '../src/convert.js';

const PATCH_TOOL = {
  type: 'custom',
  name: 'apply_patch',
  description: 'The `apply_patch` tool can be used to edit files. This is a FREEFORM tool, so do not wrap the patch in JSON.',
  format: { type: 'grammar', syntax: 'lark', definition: 'start: begin_patch hunk+ end_patch' },
};
const EXEC_TOOL = {
  type: 'function',
  name: 'exec_command',
  description: 'Runs a command.',
  parameters: { type: 'object', properties: { cmd: { type: 'string' } }, required: ['cmd'] },
};

describe('convertTools', () => {
  it('keeps function tools and gives a freeform tool one string field with its grammar', () => {
    const names = new ToolNames();
    const tools = convertTools([EXEC_TOOL, PATCH_TOOL, { type: 'web_search' }], names);
    expect(tools.map((t) => t.name)).toEqual(['exec_command', 'apply_patch']);
    expect(tools[0]!.input_schema).toEqual(EXEC_TOOL.parameters);
    expect(tools[1]!.input_schema).toEqual({ type: 'object', properties: { input: { type: 'string' } }, required: ['input'] });
    expect(tools[1]!.description).not.toContain('FREEFORM');
    expect(tools[1]!.description).toContain('start: begin_patch hunk+ end_patch');
    expect(names.isFreeform('apply_patch')).toBe(true);
  });

  it('rewrites names the Messages API refuses and maps them back', () => {
    const names = new ToolNames();
    const [t] = convertTools([{ ...EXEC_TOOL, name: 'docs.search/v2' }], names);
    expect(t!.name).toBe('docs_search_v2');
    expect(names.original('docs_search_v2')).toBe('docs.search/v2');
  });
});

describe('convertInput', () => {
  it('moves leading developer messages to system and later ones to user text', () => {
    const { system, messages } = convertInput(
      {
        input: [
          { type: 'message', role: 'developer', content: [{ type: 'input_text', text: 'base' }] },
          { type: 'message', role: 'developer', content: [{ type: 'input_text', text: 'skills' }] },
          { type: 'message', role: 'user', content: [{ type: 'input_text', text: 'env' }] },
          { type: 'message', role: 'user', content: [{ type: 'input_text', text: 'task' }] },
          { type: 'message', role: 'developer', content: [{ type: 'input_text', text: 'later' }] },
        ],
      },
      new ToolNames(),
    );
    expect(system).toEqual([
      { type: 'text', text: 'base' },
      { type: 'text', text: 'skills' },
    ]);
    expect(messages).toEqual([
      {
        role: 'user',
        content: [
          { type: 'text', text: 'env' },
          { type: 'text', text: 'task' },
          { type: 'text', text: 'later' },
        ],
      },
    ]);
  });

  it('turns calls and outputs into tool_use and tool_result, thinking first, results first', () => {
    const thinking = encodeThinking({ type: 'thinking', thinking: '', signature: 'sig' } as Anthropic.ThinkingBlock);
    const { messages } = convertInput(
      {
        input: [
          { type: 'message', role: 'user', content: 'go' },
          { type: 'reasoning', summary: [], encrypted_content: thinking },
          { type: 'function_call', call_id: 'c1', name: 'exec_command', arguments: '{"cmd":"ls"}' },
          { type: 'custom_tool_call', call_id: 'c2', name: 'apply_patch', input: '*** Begin Patch\n' },
          { type: 'message', role: 'developer', content: 'note' },
          { type: 'function_call_output', call_id: 'c1', output: 'a.txt\n' },
          { type: 'custom_tool_call_output', call_id: 'c2', output: 'Exit code: 0\n' },
        ],
      },
      new ToolNames(),
    );
    expect(messages).toEqual([
      { role: 'user', content: [{ type: 'text', text: 'go' }] },
      {
        role: 'assistant',
        content: [
          { type: 'thinking', thinking: '', signature: 'sig' },
          { type: 'tool_use', id: 'c1', name: 'exec_command', input: { cmd: 'ls' } },
          { type: 'tool_use', id: 'c2', name: 'apply_patch', input: { input: '*** Begin Patch\n' } },
        ],
      },
      {
        role: 'user',
        content: [
          { type: 'tool_result', tool_use_id: 'c1', content: 'a.txt\n' },
          { type: 'tool_result', tool_use_id: 'c2', content: 'Exit code: 0\n' },
          { type: 'text', text: 'note' },
        ],
      },
    ]);
  });

  it('skips reasoning it did not write', () => {
    const { messages } = convertInput(
      { input: [{ type: 'message', role: 'user', content: 'go' }, { type: 'reasoning', encrypted_content: 'gAAAAB-opaque' }] },
      new ToolNames(),
    );
    expect(messages).toEqual([{ role: 'user', content: [{ type: 'text', text: 'go' }] }]);
  });

  it('is deterministic, so a replayed history is byte identical', () => {
    const req = {
      input: [
        { type: 'message', role: 'user', content: 'go' },
        { type: 'function_call', call_id: 'c1', name: 'exec_command', arguments: '{"cmd":"ls"}' },
        { type: 'function_call_output', call_id: 'c1', output: 'x' },
      ],
    } as Pick<ResponsesRequest, 'input'>;
    expect(JSON.stringify(convertInput(req, new ToolNames()))).toBe(JSON.stringify(convertInput(req, new ToolNames())));
  });
});

describe('convertRequest', () => {
  it('sets adaptive thinking, the effort, automatic caching and auto tool choice', () => {
    const p = convertRequest(
      {
        model: 'claude-sonnet-5-5',
        input: [{ type: 'message', role: 'user', content: 'go' }],
        tools: [EXEC_TOOL],
        reasoning: { effort: 'medium', summary: 'auto' },
        parallel_tool_calls: true,
      },
      new ToolNames(),
      { maxTokens: 64000 },
    );
    expect(p).toMatchObject({
      model: 'claude-sonnet-5-5',
      max_tokens: 64000,
      thinking: { type: 'adaptive' },
      output_config: { effort: 'medium' },
      cache_control: { type: 'ephemeral' },
      tool_choice: { type: 'auto' },
    });
    expect(p.system).toBeUndefined();
  });

  it('passes no effort the Messages API does not know', () => {
    const p = convertRequest(
      { model: 'm', input: [{ type: 'message', role: 'user', content: 'go' }], reasoning: { effort: 'minimal' } },
      new ToolNames(),
      { maxTokens: 1000 },
    );
    expect(p.output_config).toBeUndefined();
  });
});

describe('convertOutput', () => {
  it('maps thinking, text, function and freeform calls in order', () => {
    const names = new ToolNames();
    convertTools([EXEC_TOOL, PATCH_TOOL], names);
    const items = convertOutput(
      {
        id: 'msg_1',
        content: [
          { type: 'thinking', thinking: 'plan', signature: 's' },
          { type: 'text', text: 'Reading.', citations: null },
          { type: 'tool_use', id: 't1', name: 'exec_command', input: { cmd: 'cat a.txt' } },
          { type: 'tool_use', id: 't2', name: 'apply_patch', input: { input: '*** Begin Patch\n*** End Patch\n' } },
        ] as Anthropic.ContentBlock[],
      },
      names,
    );
    expect(items.map((i) => i.type)).toEqual(['reasoning', 'message', 'function_call', 'custom_tool_call']);
    expect(items[0]).toMatchObject({ summary: [{ type: 'summary_text', text: 'plan' }] });
    expect(items[2]).toMatchObject({ call_id: 't1', arguments: '{"cmd":"cat a.txt"}' });
    expect(items[3]).toMatchObject({ call_id: 't2', input: '*** Begin Patch\n*** End Patch\n' });
  });

  it('round-trips a thinking block through a reasoning item', () => {
    const names = new ToolNames();
    const [item] = convertOutput({ id: 'm', content: [{ type: 'redacted_thinking', data: 'opaque' }] as Anthropic.ContentBlock[] }, names);
    const { messages } = convertInput(
      { input: [{ type: 'message', role: 'user', content: 'go' }, item as never] },
      names,
    );
    expect(messages[1]).toEqual({ role: 'assistant', content: [{ type: 'redacted_thinking', data: 'opaque' }] });
  });
});

describe('convertUsage', () => {
  it('counts cache reads and writes as input and reports reads as cached', () => {
    expect(
      convertUsage({ input_tokens: 10, cache_read_input_tokens: 900, cache_creation_input_tokens: 90, output_tokens: 50 } as Anthropic.Usage),
    ).toEqual({
      input_tokens: 1000,
      input_tokens_details: { cached_tokens: 900 },
      output_tokens: 50,
      output_tokens_details: { reasoning_tokens: 0 },
      total_tokens: 1050,
    });
  });
});
