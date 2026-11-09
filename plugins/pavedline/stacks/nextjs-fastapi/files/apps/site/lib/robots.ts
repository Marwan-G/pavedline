/** AI-crawler user agents the site treats as a policy choice. Placeholder: step 4's decision (questions.md, "Website, blog and SEO") sets it. */
export const AI_CRAWLERS = ['GPTBot', 'ClaudeBot', 'CCBot', 'Google-Extended', 'PerplexityBot']

/** Public only when the environment says so; every other origin (local, staging) is disallow-all and noindex. */
export function isIndexable(env: Record<string, string | undefined> = process.env): boolean {
  return env.SITE_INDEXABLE === 'true'
}

export function siteOrigin(env: Record<string, string | undefined> = process.env): string {
  return (env.SITE_ORIGIN ?? 'http://localhost:3000').replace(/\/+$/, '')
}

export type RobotsRules = {
  rules: { userAgent: string | string[]; allow?: string; disallow?: string }[]
  sitemap?: string
}

export function robotsFor(env: Record<string, string | undefined> = process.env): RobotsRules {
  if (!isIndexable(env)) return { rules: [{ userAgent: '*', disallow: '/' }] }
  // AI_CRAWLER_POLICY=allow (default) or disallow; the product's decision from step 4 replaces the default.
  const aiRule =
    env.AI_CRAWLER_POLICY === 'disallow' ? [{ userAgent: AI_CRAWLERS, disallow: '/' }] : []
  return {
    rules: [{ userAgent: '*', allow: '/' }, ...aiRule],
    sitemap: `${siteOrigin(env)}/sitemap.xml`,
  }
}
