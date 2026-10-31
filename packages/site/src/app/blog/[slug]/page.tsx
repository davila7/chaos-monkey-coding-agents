import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SiteNav } from '@/components/SiteNav';
import { formatDate, loadPosts, renderPost } from '@/lib/blog';
import { ogImageMeta } from '@/lib/og';

type Params = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return loadPosts().map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const post = loadPosts().find((p) => p.slug === slug);
  if (!post) return {};
  const images = ogImageMeta(`/blog/${post.slug}/og.png`);
  return {
    title: `${post.title} | Chaos Monkey for Coding Agents`,
    description: post.summary,
    openGraph: { type: 'article', title: post.title, description: post.summary, url: `/blog/${post.slug}/`, publishedTime: post.date, images },
    twitter: { card: 'summary_large_image', title: post.title, description: post.summary, images },
  };
}

export default async function PostPage({ params }: Params) {
  const { slug } = await params;
  const post = loadPosts().find((p) => p.slug === slug);
  if (!post) notFound();
  return (
    <>
      <SiteNav />
      <main className="wrap post-wrap">
        <a className="back" href="/blog/">
          &larr; All posts
        </a>
        <article className="post">
          <time dateTime={post.date}>{formatDate(post.date)}</time>
          <h1>{post.title}</h1>
          {/* Posts are repository content reviewed in PRs, not user input. */}
          <div dangerouslySetInnerHTML={{ __html: renderPost(post) }} />
        </article>
      </main>
    </>
  );
}
