import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui'],
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular'],
      },
      colors: {
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
        'pulse-ring': { '0%': { transform: 'scale(0.9)', opacity: '0.7' }, '100%': { transform: 'scale(1.8)', opacity: '0' } },
      },
      animation: {
        aurora: 'aurora 18s ease-in-out infinite',
        shimmer: 'shimmer 2.4s linear infinite',
        dash: 'dash 1s linear infinite',
        'pulse-ring': 'pulse-ring 1.6s cubic-bezier(0.2,0.6,0.4,1) infinite',
      },
    },
  },
  plugins: [],
}
export default config
