'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/* Minimal typings for the (still vendor-prefixed) Web Speech API - not part of lib.dom. */
interface SRAlternative { transcript: string }
interface SRResult { isFinal: boolean; 0: SRAlternative; length: number }
interface SREvent { resultIndex: number; results: ArrayLike<SRResult> }
interface SRErrorEvent { error: string }
interface SRInstance {
  lang: string; continuous: boolean; interimResults: boolean; maxAlternatives: number
  onstart: (() => void) | null; onend: (() => void) | null; onerror: ((e: SRErrorEvent) => void) | null; onresult: ((e: SREvent) => void) | null
  start: () => void; stop: () => void; abort: () => void
}
type SRCtor = new () => SRInstance

const getCtor = (): SRCtor | null => {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: SRCtor; webkitSpeechRecognition?: SRCtor }
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access was blocked. Allow the microphone for this site in your browser settings, then try again.',
  'service-not-allowed': 'Speech recognition is not allowed in this browser or context.',
  'audio-capture': 'No microphone was found. Plug one in and try again.',
  'network': 'Speech recognition needs a network connection in this browser.',
  'language-not-supported': 'This language is not supported by the browser speech engine.',
}

/**
 * Native browser dictation (window.SpeechRecognition / webkitSpeechRecognition) - no third-party service or key.
 * `onFinal` receives every finalised phrase; interim words are exposed for a live preview. Permission denials and other
 * failures surface as a friendly `error` string instead of throwing.
 */
export function useSpeechToText(onFinal: (text: string) => void, lang?: string) {
  const [supported, setSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const rec = useRef<SRInstance | null>(null)
  const wanted = useRef(false)               // user intent: true between "start" and "stop" clicks
  const cb = useRef(onFinal)
  cb.current = onFinal

  // feature-detect after mount so SSR markup and the first client render agree
  useEffect(() => { setSupported(!!getCtor()) }, [])

  const stop = useCallback(() => {
    wanted.current = false
    rec.current?.stop()
    setInterim('')
  }, [])

  const start = useCallback(() => {
    const Ctor = getCtor()
    if (!Ctor) { setError('Voice input is not supported in this browser. Try Chrome, Edge or Safari.'); return }
    if (wanted.current) return
    setError(null)
    setInterim('')
    const r = new Ctor()
    r.lang = lang || (typeof navigator !== 'undefined' && navigator.language) || 'en-US'
    r.continuous = true
    r.interimResults = true
    r.maxAlternatives = 1
    r.onstart = () => setListening(true)
    r.onresult = (e) => {
      let live = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        const text = res[0]?.transcript ?? ''
        if (res.isFinal) { const t = text.trim(); if (t) cb.current(t) } else live += text
      }
      setInterim(live.trim())
    }
    r.onerror = (e) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return        // benign: silence timeout / manual stop
      wanted.current = false
      setError(ERRORS[e.error] || `Voice input stopped (${e.error}).`)
    }
    r.onend = () => {
      // Chrome ends continuous sessions on its own after a pause: keep going while the user has not pressed stop
      if (wanted.current) { try { r.start(); return } catch { /* fall through */ } }
      wanted.current = false
      setListening(false)
      setInterim('')
    }
    rec.current = r
    wanted.current = true
    try { r.start() } catch { wanted.current = false; setListening(false); setError('Could not start the microphone. Please try again.') }
  }, [lang])

  const toggle = useCallback(() => (wanted.current ? stop() : start()), [start, stop])

  useEffect(() => () => { wanted.current = false; rec.current?.abort() }, [])

  return { supported, listening, interim, error, start, stop, toggle }
}
