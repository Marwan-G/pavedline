import type { MetadataRoute } from 'next'

// The web app is never public: disallow everything (the headers say noindex too).
export default function robots(): MetadataRoute.Robots {
  return { rules: { userAgent: '*', disallow: '/' } }
}
