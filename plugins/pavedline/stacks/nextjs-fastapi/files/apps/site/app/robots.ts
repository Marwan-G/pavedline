import type { MetadataRoute } from 'next'
import { robotsFor } from '@/lib/robots'

// Read at request time: one image, the environment decides whether the origin is public.
export const dynamic = 'force-dynamic'

export default function robots(): MetadataRoute.Robots {
  return robotsFor()
}
