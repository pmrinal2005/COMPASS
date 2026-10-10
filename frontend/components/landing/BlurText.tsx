'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

type Props = { text: string; className?: string; delay?: number }

/** Word-by-word blur-in headline reveal (triggers when scrolled into view). */
export function BlurText({ text, className, delay = 100 }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true) }, { threshold: 0.2 })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <span ref={ref} className={className}>
      {text.split(' ').map((word, i) => (
        <motion.span
          key={`${word}-${i}`}
          className="mr-[0.25em] inline-block"
          initial={{ filter: 'blur(10px)', opacity: 0, y: 50 }}
          animate={visible ? { filter: ['blur(5px)', 'blur(0px)'], opacity: [0.5, 1], y: [-5, 0] } : { filter: 'blur(10px)', opacity: 0, y: 50 }}
          transition={{ duration: 0.7, delay: (i * delay) / 1000, ease: 'easeOut' }}
        >
          {word}
        </motion.span>
      ))}
    </span>
  )
}
