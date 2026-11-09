import { css } from '@app/tokens'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import { siteOrigin } from '@/lib/robots'

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin()),
  title: { default: 'Example', template: '%s | Example' },
  description: 'The public website.',
  openGraph: { type: 'website', siteName: 'Example' },
}

const base = `${css}
body { margin: 0; font-family: system-ui, sans-serif; background: var(--color-background, Canvas); color: var(--color-text, CanvasText); }
main { max-width: 42rem; margin: 0 auto; padding: 2rem 1rem; }
nav a { margin-right: 1rem; }
`

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <style>{base}</style>
      </head>
      <body>
        <header>
          <nav aria-label="Main">
            <a href="/">Home</a>
            <a href="/blog">Blog</a>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  )
}
