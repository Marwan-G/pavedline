import type { Metadata } from 'next'
import { posts } from '@/lib/posts'

export const metadata: Metadata = { title: 'Blog', description: 'Posts from the team.' }

export default function BlogIndex() {
  return (
    <>
      <h1>Blog</h1>
      <ul>
        {posts.map((p) => (
          <li key={p.slug}>
            <a href={`/blog/${p.slug}`}>{p.title}</a> <time dateTime={p.date}>{p.date}</time>
            <p>{p.description}</p>
          </li>
        ))}
      </ul>
    </>
  )
}
