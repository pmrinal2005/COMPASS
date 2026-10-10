'use client'

import { motion } from 'framer-motion'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

/** Sleek Light/Dark switch for the top navigation bar. */
export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const light = theme === 'light'
  return (
    <button
      type="button"
      role="switch"
      aria-checked={light}
      aria-label={light ? 'Switch to dark mode' : 'Switch to light mode'}
      title={light ? 'Light mode · click for dark' : 'Dark mode · click for light'}
      id="theme-toggle"
      onClick={toggle}
      className={cn(
        'relative inline-flex h-8 w-[58px] shrink-0 items-center rounded-full border p-0.5 transition-colors',
        light ? 'border-amber-300/50 bg-amber-300/20' : 'border-white/10 bg-white/[0.04]',
      )}
    >
      <Sun size={12} className={cn('pointer-events-none absolute left-2 transition-opacity', light ? 'opacity-0' : 'text-slate-400 opacity-100')} />
      <Moon size={12} className={cn('pointer-events-none absolute right-2 transition-opacity', light ? 'text-slate-400 opacity-100' : 'opacity-0')} />
      <motion.span
        className={cn('relative z-10 grid h-6 w-6 place-items-center rounded-full shadow-md', light ? 'bg-amber-400 text-[#fff]' : 'bg-violet-500 text-[#fff]')}
        animate={{ x: light ? 26 : 0 }}
        transition={{ type: 'spring', stiffness: 500, damping: 32 }}
      >
        {light ? <Sun size={13} /> : <Moon size={13} />}
      </motion.span>
    </button>
  )
}
