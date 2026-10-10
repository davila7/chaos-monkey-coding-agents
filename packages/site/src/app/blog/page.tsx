import type { Metadata } from 'next';
import { SiteNav } from '@/components/SiteNav';
import { formatDate, loadPosts } from '@/lib/blog';

export const metadata: Metadata = { title: 'Blog | Chaos Monkey for Coding Agents' };

export default function BlogIndex() {
  const posts = loadPosts();
  return (
    <>
      <SiteNav />
      <main className="wrap post-wrap">
        <h1 className="blog-title">Building the benchmark</h1>
        <p className="blog-lede">Notes on how the benchmark is put together, written as it happens.</p>
        <ul className="post-list">
          {posts.map((p) => (
            <li key={p.slug}>
              <a href={`/blog/${p.slug}/`}>
                <time dateTime={p.date}>{formatDate(p.date)}</time>
                <b>{p.title}</b>
                <span>{p.summary}</span>
              </a>
            </li>
          ))}
        </ul>
      </main>
    </>
  );
}
