import type { ReactNode } from 'react'

export type IconName = 'home' | 'upload' | 'car' | 'chart' | 'history' | 'settings' | 'help' | 'sun' | 'moon' | 'file' | 'arrow' | 'check'
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    home: <><path d="m3 10 9-7 9 7v10H3Z" /><path d="M9 20v-7h6v7" /></>,
    upload: <path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" />,
    car: <path d="m5 9 2-5h10l2 5 2 2v7H3v-7Zm0 0h14M7 13h1m8 0h1M5 18v2m14-2v2" />,
    chart: <path d="M4 3v17h17M9 15v-4m5 4V7m5 8V4" />,
    history: <path d="M3 5v5h5M3 10a9 9 0 1 1 1 7M12 7v5l3 2" />,
    settings: <><path d="m9 3-1 3-3 1-2 4 2 2v4l4 3 3-1 3 1 4-3v-4l2-2-2-4-3-1-1-3Z" /><circle cx="12" cy="12" r="3" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 3h.01" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1" /></>,
    moon: <path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z" />,
    file: <path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h5" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    check: <path d="m5 12 4 4L19 6" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}
