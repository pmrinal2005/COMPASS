'use client'

import { MotionConfig } from 'framer-motion'

/** Honour the OS "reduce motion" setting for every framer-motion animation (CSS animations are handled in globals.css). */
export function Providers({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
