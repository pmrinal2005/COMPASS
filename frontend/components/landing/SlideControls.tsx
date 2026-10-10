'use client'

import { ChevronLeft, ChevronRight } from 'lucide-react'

type Props = { index: number; total: number; label: string; onPrev: () => void; onNext: () => void }

export function SlideControls({ index, total, label, onPrev, onNext }: Props) {
  const n = String(index + 1).padStart(2, '0')
  const t = String(total).padStart(2, '0')
  return (
    <div className="pointer-events-none absolute bottom-0 left-0 right-0 z-50 px-4 pb-4 sm:px-8 sm:pb-6 lg:px-12">
      <div className="pointer-events-auto flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="shrink-0 text-xs uppercase tracking-[0.2em] text-white/30">{n} / {t}</span>
          <span className="hidden h-4 w-px bg-white/15 sm:block" />
          <span className="truncate text-xs text-white/50">{label}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1 sm:gap-1.5">
            {Array.from({ length: total }).map((_, i) => (
              <span key={i} className={`h-1 rounded-full transition-all duration-500 ${i === index ? 'w-8 bg-white sm:w-16 lg:w-24' : 'w-3 bg-white/20 hover:bg-white/40 sm:w-6 lg:w-8'}`} />
            ))}
          </div>
          <span className="h-4 w-px bg-white/15" />
          <button type="button" onClick={onPrev} disabled={index === 0} aria-label="Previous slide"
            className="flex h-8 w-8 items-center justify-center rounded-full text-white/50 hover:bg-white/10 hover:text-white disabled:opacity-20">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button type="button" onClick={onNext} disabled={index === total - 1} aria-label="Next slide"
            className="flex h-8 w-8 items-center justify-center rounded-full text-white/50 hover:bg-white/10 hover:text-white disabled:opacity-20">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
