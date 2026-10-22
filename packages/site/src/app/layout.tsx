import type { Metadata } from 'next';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/700.css';
import './globals.css';
import { FlameFavicon } from '@/components/FlameFavicon';

export const metadata: Metadata = {
  title: 'Chaos Monkey for Coding Agents',
  description: 'How coding-agent harnesses recover when their tools fail.',
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
