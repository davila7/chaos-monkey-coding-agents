'use client';

import { useEffect } from 'react';
import { FLAME_FRAMES, FLAME_MS, flameFrame } from '@/lib/flame';

const SIZE = 64;

async function still(svg: string): Promise<string> {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = SIZE;
    const ctx = canvas.getContext('2d')!;
    const w = (SIZE * 700) / 724;
    ctx.drawImage(img, (SIZE - w) / 2, 0, w, SIZE);
    return canvas.toDataURL('image/png');
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function FlameFavicon() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    let timer: number | undefined;
    let stopped = false;
    (async () => {
      const svg = await (await fetch('/monkey.svg')).text();
      const frames = await Promise.all(Array.from({ length: FLAME_FRAMES }, (_, k) => still(flameFrame(svg, k))));
      if (stopped) return;
      let link = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      link.type = 'image/png';
      let k = 0;
      timer = window.setInterval(() => {
        if (document.hidden) return;
        link!.href = frames[(k = (k + 1) % FLAME_FRAMES)]!;
      }, FLAME_MS);
    })().catch(() => {});
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);
  return null;
}
