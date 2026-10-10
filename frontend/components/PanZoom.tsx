'use client'

import { useCallback, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState, forwardRef } from 'react'
import { Maximize, Minus, Plus, Scan } from 'lucide-react'
import { cn } from '@/lib/utils'

interface View { x: number; y: number; k: number }
export interface PanZoomHandle { fit: () => void }

const MIN_K = 0.25
const MAX_K = 4
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v))

/**
 * Google-Maps-style viewport: drag to pan, wheel / pinch / +− buttons to zoom (anchored on the cursor), arrow keys to pan, 0 to fit.
 * `width`/`height` are the natural pixel size of the content; the content is auto-fitted until the user touches the view, so a live-growing
 * graph keeps re-centering itself right up to the first manual pan/zoom.
 */
export const PanZoom = forwardRef<PanZoomHandle, { width: number; height: number; children: React.ReactNode; className?: string; label?: string }>(
  function PanZoom({ width, height, children, className, label = 'Pannable and zoomable canvas' }, ref) {
    const box = useRef<HTMLDivElement>(null)
    const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 })
    const viewRef = useRef(view)
    viewRef.current = view
    const touched = useRef(false)
    const [dragging, setDragging] = useState(false)
    const pointers = useRef(new Map<number, { x: number; y: number }>())
    const pinch = useRef<{ d: number; k: number } | null>(null)

    const apply = useCallback((v: View) => { viewRef.current = v; setView(v) }, [])

    const fit = useCallback(() => {
      const el = box.current
      if (!el) return
      // clientWidth/Height ignore ancestor CSS transforms (the modal scales in), unlike getBoundingClientRect
      const vw = el.clientWidth, vh = el.clientHeight
      if (!vw || !vh) return
      const k = clamp(Math.min(vw / width, vh / height) * 0.94, MIN_K, 1.6)
      apply({ k, x: (vw - width * k) / 2, y: (vh - height * k) / 2 })
    }, [width, height, apply])

    useImperativeHandle(ref, () => ({ fit }), [fit])

    // auto-fit on mount / when the content grows / when the viewport resizes (until the user takes over)
    useLayoutEffect(() => { if (!touched.current) fit() }, [fit])
    useEffect(() => {
      const el = box.current
      if (!el || typeof ResizeObserver === 'undefined') return
      const ro = new ResizeObserver(() => { if (!touched.current) fit() })
      ro.observe(el)
      return () => ro.disconnect()
    }, [fit])

    /** zoom by `factor` keeping the viewport point (cx, cy) fixed */
    const zoomAt = useCallback((factor: number, cx: number, cy: number) => {
      const v = viewRef.current
      const k = clamp(v.k * factor, MIN_K, MAX_K)
      const r = k / v.k
      touched.current = true
      apply({ k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r })
    }, [apply])

    const zoomCenter = (factor: number) => {
      const el = box.current
      if (el) zoomAt(factor, el.clientWidth / 2, el.clientHeight / 2)
    }

    // wheel must be a non-passive native listener so we can stop the page from scrolling behind the modal
    useEffect(() => {
      const el = box.current
      if (!el) return
      const onWheel = (e: WheelEvent) => {
        e.preventDefault()
        const r = el.getBoundingClientRect()
        const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 400 : 1
        zoomAt(Math.exp(-e.deltaY * unit * (e.ctrlKey ? 0.01 : 0.0016)), e.clientX - r.left, e.clientY - r.top)
      }
      el.addEventListener('wheel', onWheel, { passive: false })
      return () => el.removeEventListener('wheel', onWheel)
    }, [zoomAt])

    const onPointerDown = (e: React.PointerEvent) => {
      if ((e.target as HTMLElement).closest('[data-pz-ui]')) return
      box.current?.setPointerCapture(e.pointerId)
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
      if (pointers.current.size === 2) {
        const [a, b] = [...pointers.current.values()]
        pinch.current = { d: Math.hypot(a.x - b.x, a.y - b.y), k: viewRef.current.k }
      }
      setDragging(true)
    }
    const onPointerMove = (e: React.PointerEvent) => {
      const p = pointers.current.get(e.pointerId)
      if (!p) return
      const dx = e.clientX - p.x, dy = e.clientY - p.y
      pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
      touched.current = true
      if (pointers.current.size >= 2 && pinch.current) {
        const [a, b] = [...pointers.current.values()]
        const d = Math.hypot(a.x - b.x, a.y - b.y)
        const r = box.current!.getBoundingClientRect()
        const target = clamp(pinch.current.k * (d / pinch.current.d), MIN_K, MAX_K)
        zoomAt(target / viewRef.current.k, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top)
      } else {
        const v = viewRef.current
        apply({ ...v, x: v.x + dx, y: v.y + dy })
      }
    }
    const onPointerUp = (e: React.PointerEvent) => {
      pointers.current.delete(e.pointerId)
      if (pointers.current.size < 2) pinch.current = null
      if (pointers.current.size === 0) setDragging(false)
    }
    const onKeyDown = (e: React.KeyboardEvent) => {
      const step = 60, v = viewRef.current
      const pan = (dx: number, dy: number) => { touched.current = true; apply({ ...v, x: v.x + dx, y: v.y + dy }) }
      if (e.key === 'ArrowLeft') pan(step, 0)
      else if (e.key === 'ArrowRight') pan(-step, 0)
      else if (e.key === 'ArrowUp') pan(0, step)
      else if (e.key === 'ArrowDown') pan(0, -step)
      else if (e.key === '+' || e.key === '=') zoomCenter(1.25)
      else if (e.key === '-' || e.key === '_') zoomCenter(0.8)
      else if (e.key === '0') { touched.current = false; fit() }
      else return
      e.preventDefault()
    }

    return (
      <div
        ref={box}
        tabIndex={0}
        role="application"
        aria-label={`${label}. Drag to pan, scroll or use the plus and minus keys to zoom, zero to fit.`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={(e) => { const r = box.current!.getBoundingClientRect(); zoomAt(1.6, e.clientX - r.left, e.clientY - r.top) }}
        onKeyDown={onKeyDown}
        className={cn('relative select-none overflow-hidden outline-none focus-visible:ring-1 focus-visible:ring-violet-400/50', dragging ? 'cursor-grabbing' : 'cursor-grab', className)}
        style={{ touchAction: 'none' }}
      >
        <div style={{ width, height, transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, transformOrigin: '0 0', willChange: 'transform' }}>
          {children}
        </div>

        {/* controls */}
        <div data-pz-ui className="absolute bottom-3 right-3 flex flex-col items-center gap-1 rounded-xl border border-white/10 bg-surface/80 p-1 shadow-lg backdrop-blur">
          <button type="button" className="btn-ghost !p-1.5" aria-label="Zoom in" title="Zoom in (+)" onClick={() => zoomCenter(1.25)}><Plus size={14} /></button>
          <span className="font-mono text-[10px] text-slate-400" aria-live="off">{Math.round(view.k * 100)}%</span>
          <button type="button" className="btn-ghost !p-1.5" aria-label="Zoom out" title="Zoom out (−)" onClick={() => zoomCenter(0.8)}><Minus size={14} /></button>
          <button type="button" className="btn-ghost !p-1.5" aria-label="Fit graph to view" title="Fit to view (0)" onClick={() => { touched.current = false; fit() }}><Scan size={14} /></button>
          <button type="button" className="btn-ghost !p-1.5" aria-label="Actual size" title="100%" onClick={() => {
            const el = box.current!; touched.current = true
            apply({ k: 1, x: (el.clientWidth - width) / 2, y: (el.clientHeight - height) / 2 })
          }}><Maximize size={14} /></button>
        </div>
        <div data-pz-ui className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-white/10 bg-surface/70 px-2 py-1 text-[10px] text-slate-400 backdrop-blur">
          drag to pan · scroll / pinch to zoom · double-click to zoom in · arrows move · 0 fits
        </div>
      </div>
    )
  },
)
