import type { Metadata, Viewport } from 'next'
import { Barlow, Inter, Instrument_Serif, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Providers } from '@/components/Providers'

const sans = Inter({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })
const barlow = Barlow({ subsets: ['latin'], weight: ['300', '400', '500', '600'], variable: '--font-barlow', display: 'swap' })
const instrument = Instrument_Serif({ subsets: ['latin'], weight: '400', style: ['normal', 'italic'], variable: '--font-instrument', display: 'swap' })

export const metadata: Metadata = {
  title: 'COMPASS — One Decision Engine, Infinite Verticals',
  description: 'SerpApi-native multi-agent operating system: Plan → Search → Compare → Act.',
}
export const viewport: Viewport = { themeColor: '#05060b' }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${mono.variable} ${barlow.variable} ${instrument.variable}`}>
      <head>
        {/* apply the saved Light/Dark choice before first paint, on the dashboard only (the landing page stays dark) */}
        <script dangerouslySetInnerHTML={{ __html: "try{if(location.pathname.indexOf('/dashboard')===0&&localStorage.getItem('compass-theme')==='light')document.documentElement.setAttribute('data-theme','light')}catch(e){}" }} />
      </head>
      <body className="min-h-screen font-sans"><Providers>{children}</Providers></body>
    </html>
  )
}
