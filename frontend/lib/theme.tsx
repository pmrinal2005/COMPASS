'use client'

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from 'react'

export type Theme = 'dark' | 'light'
export const THEME_KEY = 'compass-theme'

interface Ctx { theme: Theme; setTheme: (t: Theme) => void; toggle: () => void }
const ThemeCtx = createContext<Ctx>({ theme: 'dark', setTheme: () => {}, toggle: () => {} })

// useLayoutEffect warns during SSR; fall back to useEffect on the server.
const useIsoLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect

/**
 * Dashboard-scoped Light/Dark theme. It sets `data-theme="light"` on <html> (CSS variables in globals.css do the rest) and removes it again
 * on unmount, so the cinematic landing page (`/`) is never affected. The choice is persisted in localStorage; the inline script in the root
 * layout applies it before first paint on /dashboard to avoid a flash.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('dark')
  const [ready, setReady] = useState(false)

  useIsoLayoutEffect(() => {
    let t: Theme = 'dark'
    try { if (localStorage.getItem(THEME_KEY) === 'light') t = 'light' } catch { /* storage blocked: keep dark */ }
    setThemeState(t)
    setReady(true)
  }, [])

  useIsoLayoutEffect(() => {
    if (!ready) return
    const el = document.documentElement
    if (theme === 'light') el.setAttribute('data-theme', 'light')
    else el.removeAttribute('data-theme')
  }, [theme, ready])

  // leaving the dashboard (e.g. back to the landing page) must restore the dark landing look
  useIsoLayoutEffect(() => () => document.documentElement.removeAttribute('data-theme'), [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    try { localStorage.setItem(THEME_KEY, t) } catch { /* ignore */ }
  }, [])
  const toggle = useCallback(() => setTheme(theme === 'dark' ? 'light' : 'dark'), [theme, setTheme])
  const value = useMemo(() => ({ theme, setTheme, toggle }), [theme, setTheme, toggle])
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>
}

export const useTheme = () => useContext(ThemeCtx)
