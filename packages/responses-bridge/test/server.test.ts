import Anthropic from '@anthropic-ai/sdk';
import { mkdtempSync, readFileSync } from 'node:fs';
import type { AddressInfo } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { serve, type BridgeConfig } from '../src/server.js';

type Handler = (e: { type: string; message: { id: string } }) => void;

function fakeClient(result: Anthropic.Message | Error, seen: unknown[] = []): BridgeConfig['client'] {
  return {
    messages: {
      stream(params: unknown) {
        seen.push(params);
        const handlers: Handler[] = [];
        return {
          on(_: string, h: Handler) {
            handlers.push(h);
            return this;
          },
          async finalMessage() {
            if (result instanceof Error) throw result;
            for (const h of handlers) h({ type: 'message_start', message: { id: result.id } });
            return result;
          },
        };
      },
    } as unknown as Anthropic['messages'],
  };
}

const servers: { close(): void }[] = [];
afterEach(() => servers.splice(0).forEach((s) => s.close()));

async function post(cfg: BridgeConfig, payload: unknown) {
  const server = await serve(cfg, 0);
  servers.push(server);
  const { port } = server.address() as AddressInfo;
  return fetch(`http://127.0.0.1:${port}/v1/responses`, { method: 'POST', body: JSON.stringify(payload) });
}

function events(text: string): { type: string; [k: string]: unknown }[] {
  return text
    .split('\n\n')
    .filter((c) => c.includes('data: '))
    .map((c) => JSON.parse(c.slice(c.indexOf('data: ') + 6)) as { type: string });
}

const MESSAGE = {
  id: 'msg_abc',
  type: 'message',
  role: 'assistant',
  model: 'claude-sonnet-5-5',
  stop_reason: 'tool_use',
  stop_sequence: null,
  content: [{ type: 'tool_use', id: 'toolu_1', name: 'exec_command', input: { cmd: 'ls' } }],
  usage: { input_tokens: 5, cache_read_input_tokens: 100, cache_creation_input_tokens: 20, output_tokens: 7 },
} as unknown as Anthropic.Message;

describe('serve', () => {
  it('answers a Responses request as an event stream and logs usage', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'bridge-'));
    const seen: unknown[] = [];
    const res = await post(
      { client: fakeClient(MESSAGE, seen), maxTokens: 1000, usageLog: join(dir, 'usage.jsonl') },
      { model: 'claude-sonnet-5-5', input: [{ type: 'message', role: 'user', content: 'go' }], tools: [{ type: 'function', name: 'exec_command', parameters: { type: 'object' } }] },
    );
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('text/event-stream');
    const ev = events(await res.text());
    expect(ev.map((e) => e.type)).toEqual(['response.created', 'response.output_item.added', 'response.output_item.done', 'response.completed']);
    expect(ev[2]).toMatchObject({ item: { type: 'function_call', call_id: 'toolu_1', name: 'exec_command', arguments: '{"cmd":"ls"}' } });
    expect(ev[3]).toMatchObject({ response: { id: 'msg_abc', usage: { input_tokens: 125, input_tokens_details: { cached_tokens: 100 }, output_tokens: 7 } } });
    expect(seen[0]).toMatchObject({ model: 'claude-sonnet-5-5', max_tokens: 1000 });
    const logged = JSON.parse(readFileSync(join(dir, 'usage.jsonl'), 'utf8').trim()) as Record<string, unknown>;
    expect(logged).toMatchObject({ id: 'msg_abc', model: 'claude-sonnet-5-5', usage: MESSAGE.usage });
  });

  it('reports a cut response as incomplete', async () => {
    const res = await post(
      { client: fakeClient({ ...MESSAGE, stop_reason: 'max_tokens', content: [{ type: 'text', text: 'par', citations: null }] } as Anthropic.Message), maxTokens: 10 },
      { model: 'm', input: [{ type: 'message', role: 'user', content: 'go' }] },
    );
    const ev = events(await res.text());
    expect(ev.at(-1)).toMatchObject({ type: 'response.incomplete', response: { incomplete_details: { reason: 'max_output_tokens' } } });
  });

  it('passes the status of a refused model request through', async () => {
    const err = new Anthropic.RateLimitError(429, { type: 'error', error: { type: 'rate_limit_error', message: 'slow down' } }, 'slow down', new Headers());
    const res = await post({ client: fakeClient(err), maxTokens: 10 }, { model: 'm', input: [] });
    expect(res.status).toBe(429);
    expect(await res.json()).toMatchObject({ error: { type: 'rate_limit_error' } });
  });

  it('refuses other routes', async () => {
    const server = await serve({ client: fakeClient(MESSAGE), maxTokens: 10 }, 0);
    servers.push(server);
    const { port } = server.address() as AddressInfo;
    expect((await fetch(`http://127.0.0.1:${port}/v1/chat/completions`, { method: 'POST', body: '{}' })).status).toBe(404);
  });
});
