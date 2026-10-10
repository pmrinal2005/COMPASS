import type { Config } from 'tailwindcss'
import colors from 'tailwindcss/colors'

/** Theme-aware colour: reads an `R G B` triplet from a CSS variable so the dashboard can flip Light/Dark at runtime.
 *  The :root defaults in globals.css equal Tailwind's stock values, so the dark UI and the landing page are unchanged. */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`
const themed = <K extends keyof typeof colors>(family: K, shades: number[]) => ({
  ...(colors[family] as unknown as Record<string, string>),
  ...Object.fromEntries(shades.map((s) => [String(s), v(`${family}-${s}`)])),
})

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular'],
        heading: ['var(--font-instrument)', 'Instrument Serif', 'serif'],
        body: ['var(--font-barlow)', 'Barlow', 'ui-sans-serif', 'system-ui'],
      },
      colors: {
        white: v('white'),
        black: v('black'),
        canvas: v('canvas'),
        surface: v('surface'),
        node: v('node'),
        slate: themed('slate', [100, 200, 300, 400, 600]),
        violet: themed('violet', [100, 200, 300]),
        cyan: themed('cyan', [200, 300]),
        amber: themed('amber', [50, 200, 300]),
        emerald: themed('emerald', [200, 300]),
        rose: themed('rose', [200, 300]),
        pink: themed('pink', [100, 200, 300]),
        ink: { 950: '#05060b', 900: '#090b14', 850: '#0d1020', 800: '#121630', 700: '#1b2042' },
        orchestrator: '#a78bfa',
        researcher: '#22d3ee',
        analyst: '#fbbf24',
        actor: '#34d399',
      },
      keyframes: {
        'aurora': { '0%,100%': { transform: 'translate(0,0) scale(1)' }, '50%': { transform: 'translate(4%, -3%) scale(1.08)' } },
        'shimmer': { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        'dash': { to: { strokeDashoffset: '-24' } },
        'sweep': { '0%': { transform: 'translateX(-120%)' }, '100%': { transform: 'translateX(420%)' } },
        'fade-up': { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        'glow': { '0%,100%': { boxShadow: '0 0 0 0 rgba(251,191,36,0.0)' }, '50%': { boxShadow: '0 0 18px 2px rgba(251,191,36,0.35)' } },
        'alert': { '0%,100%': { transform: 'scale(1)' }, '50%': { transform: 'scale(1.06)' } },
        'pulse-ring': { '0%': { transform: 'scale(0.9)', opacity: '0.7' }, '100%': { transform: 'scale(1.8)', opacity: '0' } },
      },
      animation: {
        aurora: 'aurora 18s ease-in-out infinite',
        shimmer: 'shimmer 2.4s linear infinite',
        dash: 'dash 1s linear infinite',
        sweep: 'sweep 1.8s ease-in-out infinite',
        'fade-up': 'fade-up .45s ease-out both',
        glow: 'glow 2.2s ease-in-out infinite',
        alert: 'alert 1.1s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(0.2,0.6,0.4,1) infinite',
      },
    },
  },
  plugins: [],
}
export default config
