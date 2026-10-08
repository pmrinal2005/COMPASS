'use client'

import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'

/** Count-up / count-down number that eases from its previous value to the new one. */
export function AnimatedNumber({ value, digits = 0, prefix = '', suffix = '', duration = 0.8, className }: {
  value: number | null | undefined; digits?: number; prefix?: string; suffix?: string; duration?: number; className?: string
}) {
  const from = useRef(0)
  const [shown, setShown] = useState<number>(typeof value === 'number' ? value : 0)
  useEffect(() => {
    if (typeof value !== 'number' || Number.isNaN(value)) return
    const c = animate(from.current, value, { duration, ease: 'easeOut', onUpdate: (v) => { from.current = v; setShown(v) } })
    return () => c.stop()
  }, [value, duration])
  if (typeof value !== 'number' || Number.isNaN(value)) return <span className={className}>—</span>
  return <span className={className}>{prefix}{shown.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}{suffix}</span>
}
