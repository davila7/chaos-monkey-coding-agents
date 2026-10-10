import { hooks } from './index.js';

// OpenCode calls every function a plugin module exports, so the entry
// exports the plugin alone.
export default {
  id: 'tt-runtime',
  server: async (input: { directory: string }) => hooks(input.directory),
};
