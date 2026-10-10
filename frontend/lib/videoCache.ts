/**
 * Parallel video pre-warmer for the cinematic landing page (ported 1:1 from the VAANI-RAKSHAK landing).
 * Fetches each clip once into a Blob URL so the hero + section videos start instantly and never re-download.
 */
type CacheEntry = { resolvedSrc: string; ready: Promise<string>; isBlob: boolean }

const cache = new Map<string, CacheEntry>()

function isLikelyCrossOrigin(src: string): boolean {
  if (typeof window === 'undefined') return true
  if (src.startsWith('/') || src.startsWith('./')) return false
  try {
    return new URL(src, window.location.href).origin !== window.location.origin
  } catch {
    return false
  }
}

export function warmVideo(src: string, priority: 'high' | 'auto' = 'auto'): Promise<string> {
  const existing = cache.get(src)
  if (existing) return existing.ready

  const entry: CacheEntry = { resolvedSrc: src, isBlob: false, ready: Promise.resolve(src) }
  entry.ready = (async () => {
    try {
      const init: RequestInit & { priority?: 'high' | 'auto' | 'low' } = {
        method: 'GET',
        credentials: 'omit',
        cache: 'force-cache',
        priority,
      }
      if (isLikelyCrossOrigin(src)) init.mode = 'cors'
      const response = await fetch(src, init)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const blobUrl = URL.createObjectURL(await response.blob())
      entry.resolvedSrc = blobUrl
      entry.isBlob = true
      return blobUrl
    } catch {
      return src
    }
  })()
  cache.set(src, entry)
  return entry.ready
}

export function warmAll(sources: string[]): Promise<string> {
  if (sources.length === 0) return Promise.resolve('')
  const [hero, ...rest] = sources
  const heroReady = warmVideo(hero, 'high')
  rest.forEach((s) => void warmVideo(s, 'high'))
  return heroReady
}

export function peekResolvedSrc(src: string): string {
  const e = cache.get(src)
  return e?.isBlob ? e.resolvedSrc : src
}

export function whenReady(src: string): Promise<string> {
  return cache.get(src)?.ready ?? warmVideo(src, 'auto')
}
