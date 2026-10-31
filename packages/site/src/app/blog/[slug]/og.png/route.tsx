import { loadPosts } from '@/lib/blog';
import { ogImage } from '@/lib/og';

export const dynamic = 'force-static';
export const dynamicParams = false;

export function generateStaticParams() {
  return loadPosts().map((p) => ({ slug: p.slug }));
}

export async function GET(_: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return ogImage(loadPosts().find((p) => p.slug === slug)!.title);
}
