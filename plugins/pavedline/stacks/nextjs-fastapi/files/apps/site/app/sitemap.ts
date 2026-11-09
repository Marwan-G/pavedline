import type { MetadataRoute } from 'next'
import { posts } from '@/lib/posts'
import { siteOrigin } from '@/lib/robots'

export const dynamic = 'force-dynamic'

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = siteOrigin()
  return [
    { url: `${origin}/` },
    { url: `${origin}/blog` },
    ...posts.map((p) => ({ url: `${origin}/blog/${p.slug}`, lastModified: p.date })),
  ]
}
