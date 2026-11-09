import { resolve } from 'node:path'
import createMDX from '@next/mdx'
import type { NextConfig } from 'next'

const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join('; ')

const config: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: resolve(import.meta.dirname, '../..'),
  transpilePackages: ['@app/tokens'],
  pageExtensions: ['ts', 'tsx', 'md', 'mdx'],
  poweredByHeader: false,
  async headers() {
    // Security headers; X-Robots-Tag is decided per request by proxy.ts, from the runtime environment, so one image
    // serves staging (not indexed) and production (indexed). script-src and style-src allow 'unsafe-inline' because
    // Next.js inlines its bootstrap script and a nonce would force every page to render per request (the site is
    // static on purpose); no eval allowance. A site that renders user-generated content moves to nonces.
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy', value: csp },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          { key: 'X-Frame-Options', value: 'DENY' },
        ],
      },
    ]
  },
}

export default createMDX({})(config)
