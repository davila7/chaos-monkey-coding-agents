import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';

export const OG_SIZE = { width: 1200, height: 630 };
const ALT = 'The chaos monkey typing at a desk while everything around it burns';

/**
 * Route handlers at `og.png` instead of the `opengraph-image` file convention: with
 * `output: 'export'` that convention writes files without an extension, which Vercel
 * serves without an image content type.
 */
export const ogImageMeta = (url: string) => [{ url, ...OG_SIZE, alt: ALT, type: 'image/png' }];

const read = (path: string) => readFileSync(join(process.cwd(), path));

/** Title sizes chosen so a title fits in the left 600 px of the 1200x630 card in at most four lines. */
export function titleSize(title: string): number {
  if (title.length <= 40) return 72;
  if (title.length <= 64) return 60;
  return 48;
}

export function ogImage(title: string): ImageResponse {
  const scene = `data:image/svg+xml;base64,${read('src/og/scene.svg').toString('base64')}`;
  const font = read('node_modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-800-normal.woff');
  return new ImageResponse(
    (
      <div style={{ display: 'flex', width: '100%', height: '100%', position: 'relative', fontFamily: 'JetBrains Mono' }}>
        <img src={scene} width={OG_SIZE.width} height={OG_SIZE.height} style={{ position: 'absolute', top: 0, left: 0 }} />
        <div style={{ display: 'flex', flexDirection: 'column', position: 'absolute', top: 64, left: 64, width: 600 }}>
          <div style={{ fontSize: 22, color: '#ff6a14', letterSpacing: 2 }}>CHAOS MONKEY FOR CODING AGENTS</div>
          <div style={{ marginTop: 28, fontSize: titleSize(title), lineHeight: 1.05, color: '#f5f0e8' }}>{title}</div>
        </div>
      </div>
    ),
    { ...OG_SIZE, fonts: [{ name: 'JetBrains Mono', data: font, weight: 800, style: 'normal' }] },
  );
}
