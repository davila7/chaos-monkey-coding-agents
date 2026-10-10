'use client';

import type { MouseEvent } from 'react';

// <details> keeps the menu usable before hydration; the click handler only closes it
// after a same-page anchor jump, which would otherwise leave the panel over the content.
export function NavMenu({ links }: { links: [string, string][] }) {
  const close = (e: MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('a')) e.currentTarget.parentElement?.removeAttribute('open');
  };
  return (
    <details className="nav-menu">
      <summary aria-label="Menu">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
          <path d="M3 5.5h14M3 10h14M3 14.5h14" />
        </svg>
      </summary>
      <div className="nav-menu-panel" onClick={close}>
        {links.map(([href, label]) => (
          <a key={label} href={href}>
            {label}
          </a>
        ))}
      </div>
    </details>
  );
}
