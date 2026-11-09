import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Home',
  description: 'What the product does, in one sentence.',
  openGraph: { title: 'Example', description: 'What the product does, in one sentence.' },
}

export default function HomePage() {
  return (
    <>
      <h1>Example</h1>
      <p>What the product does, in one sentence.</p>
    </>
  )
}
