'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { TitleSlide, ProcessSlide, CapabilitiesSlide, WhyUsSlide, StatsSlide, PromptsSlide, CtaSlide } from './slides'
import { SlideControls } from './SlideControls'

const SLIDES = [
  { id: 'intro', label: 'Introduction', Comp: TitleSlide },
  { id: 'process', label: 'How a decision happens', Comp: ProcessSlide },
  { id: 'caps', label: 'Two lenses, one engine', Comp: CapabilitiesSlide },
  { id: 'why', label: 'Why COMPASS', Comp: WhyUsSlide },
  { id: 'numbers', label: 'By the numbers', Comp: StatsSlide },
  { id: 'prompts', label: 'Try these prompts', Comp: PromptsSlide },
  { id: 'next', label: 'Open the Command Center', Comp: CtaSlide },
]

/** Horizontal snap-scrolling "product demo" deck — wheel / arrow keys / buttons, identical mechanics to VAANI-RAKSHAK. */
export function PitchDeck() {
  const [index, setIndex] = useState(0)
  const lock = useRef(false)
  const root = useRef<HTMLElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const inView = useRef(false)
  const indexRef = useRef(0)

  useEffect(() => { indexRef.current = index }, [index])

  const go = useCallback((nextIdx: number) => {
    const el = scroller.current
    if (!el || lock.current) return
    if (nextIdx < 0 || nextIdx >= SLIDES.length) return
    lock.current = true
    setIndex(nextIdx)
    indexRef.current = nextIdx
    el.scrollTo({ left: nextIdx * el.clientWidth, behavior: 'smooth' })
    window.setTimeout(() => { lock.current = false }, 720)
  }, [])

  const next = useCallback(() => go(indexRef.current + 1), [go])
  const prev = useCallback(() => go(indexRef.current - 1), [go])

  useEffect(() => {
    const el = root.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => { inView.current = e.isIntersecting && e.intersectionRatio > 0.45 }, { threshold: [0.45, 0.7] })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    const onWheel = (e: WheelEvent) => {
      if (!inView.current) return
      if (Math.abs(e.deltaY) < 24 && Math.abs(e.deltaX) < 24) return
      const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
      const i = indexRef.current
      if (delta > 0 && i < SLIDES.length - 1) { e.preventDefault(); go(i + 1) }
      else if (delta < 0 && i > 0) { e.preventDefault(); go(i - 1) }
    }
    const onKey = (e: KeyboardEvent) => {
      if (!inView.current) return
      if (['ArrowRight', 'ArrowDown', ' '].includes(e.key)) { e.preventDefault(); next() }
      else if (['ArrowLeft', 'ArrowUp'].includes(e.key)) { e.preventDefault(); prev() }
    }
    window.addEventListener('wheel', onWheel, { passive: false })
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('wheel', onWheel); window.removeEventListener('keydown', onKey) }
  }, [go, next, prev])

  useEffect(() => {
    const el = scroller.current
    if (!el) return
    const onResize = () => el.scrollTo({ left: indexRef.current * el.clientWidth, behavior: 'auto' })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const onScroll = () => {
    const el = scroller.current
    if (!el || lock.current) return
    const i = Math.round(el.scrollLeft / Math.max(el.clientWidth, 1))
    if (i !== indexRef.current && i >= 0 && i < SLIDES.length) { indexRef.current = i; setIndex(i) }
  }

  return (
    <section ref={root} id="pitch" className="relative h-screen w-full overflow-hidden bg-black">
      <div ref={scroller} className="pitch-scroller flex h-full w-full overflow-x-auto overflow-y-hidden" onScroll={onScroll}>
        {SLIDES.map(({ id, Comp }) => (
          <div key={id} className="pitch-slide relative h-full w-full shrink-0"><Comp /></div>
        ))}
      </div>
      <SlideControls index={index} total={SLIDES.length} label={SLIDES[index].label} onPrev={prev} onNext={next} />
    </section>
  )
}
