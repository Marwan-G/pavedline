export type Post = { slug: string; title: string; description: string; date: string }

/** The blog index. Each post is app/blog/<slug>/page.mdx; add it here and in the sitemap follows. */
export const posts: Post[] = [
  {
    slug: 'hello-world',
    title: 'Hello, world',
    description: 'The first post of the example blog.',
    date: '2026-01-01',
  },
]
