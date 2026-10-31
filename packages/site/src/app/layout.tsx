import type { Metadata } from 'next';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/700.css';
import './globals.css';
import { FlameFavicon } from '@/components/FlameFavicon';
import { ogImageMeta } from '@/lib/og';

const TITLE = 'Chaos Monkey for Coding Agents';
const DESCRIPTION = 'How coding-agent harnesses recover when their tools fail.';

export const metadata: Metadata = {
  // og:image URLs must be absolute; previews resolve them against the production domain.
  metadataBase: new URL('https://chaos-monkey-coding-agents.vercel.app'),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: { type: 'website', siteName: TITLE, title: TITLE, description: DESCRIPTION, images: ogImageMeta('/og.png') },
  twitter: { card: 'summary_large_image', images: ogImageMeta('/og.png') },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <FlameFavicon />
      </body>
    </html>
  );
}
