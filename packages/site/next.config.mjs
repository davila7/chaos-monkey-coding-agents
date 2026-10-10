/** @type {import('next').NextConfig} */
export default {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  // Type checking runs through `pnpm typecheck` (tsc 7); Next's in-build checker expects the TS 5 JS API.
  typescript: { ignoreBuildErrors: true },
};
