import { css } from '@app/tokens'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

export const metadata: Metadata = {
  title: 'App',
  description: 'The web app.',
  robots: { index: false, follow: false },
}

const base = `${css}
body { margin: 0; font-family: system-ui, sans-serif; background: var(--color-background, Canvas); color: var(--color-text, CanvasText); }
main { max-width: 40rem; margin: 0 auto; padding: 2rem 1rem; }
`

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <style>{base}</style>
      </head>
      <body>{children}</body>
    </html>
  )
}
