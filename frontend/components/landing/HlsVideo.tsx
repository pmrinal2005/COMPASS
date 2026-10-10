'use client'

import { useEffect, useRef, type CSSProperties } from 'react'

type Props = { src: string; className?: string; style?: CSSProperties }

/** Autoplaying muted looping video that transparently supports .m3u8 (HLS) streams via hls.js. */
export function HlsVideo({ src, className, style }: Props) {
  const ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = ref.current
    if (!video) return
    if (src.endsWith('.m3u8')) {
      if (video.canPlayType('application/vnd.apple.mpegurl')) { video.src = src; return }
      let hls: { destroy: () => void } | undefined
      let cancelled = false
      import('hls.js').then(({ default: Hls }) => {
        if (cancelled || !Hls.isSupported()) return
        const inst = new Hls()
        inst.loadSource(src)
        inst.attachMedia(video)
        hls = inst
      })
      return () => { cancelled = true; hls?.destroy() }
    }
    video.src = src
  }, [src])

  return <video ref={ref} className={className} style={style} autoPlay loop muted playsInline />
}
