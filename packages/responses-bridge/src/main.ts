import Anthropic from '@anthropic-ai/sdk';
import { serve } from './server.js';

// Started by the Harbor agent before Codex, on loopback. The key comes from
// the agent's environment and is never written to disk.
const port = Number(process.env.BRIDGE_PORT ?? '18080');
const client = new Anthropic({ maxRetries: 4 });

void serve(
  {
    client,
    maxTokens: Number(process.env.BRIDGE_MAX_TOKENS ?? '64000'),
    ...(process.env.BRIDGE_USAGE_LOG ? { usageLog: process.env.BRIDGE_USAGE_LOG } : {}),
  },
  port,
).then(() => process.stdout.write(`listening on 127.0.0.1:${port}\n`));
