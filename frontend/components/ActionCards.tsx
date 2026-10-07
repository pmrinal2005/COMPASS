'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Calendar, CheckCircle2, Download, FileText, Bell, Pencil, Plane, Send, XCircle, Eye, Briefcase, Loader2 } from 'lucide-react'
import type { ActionProposal } from '@/lib/types'
import { cn } from '@/lib/utils'

const TYPE_ICON: Record<string, any> = {
  booking_flow: Plane, application: Briefcase, calendar_invite: Calendar, document: FileText, notify: Bell, watch: Eye, email_rfq: Send,
}
const RISK: Record<string, string> = { low: 'text-emerald-300 border-emerald-400/30', medium: 'text-amber-300 border-amber-400/30', high: 'text-rose-300 border-rose-400/30' }

interface Props {
  actions: ActionProposal[]
  onApprove: (a: ActionProposal) => void
  onReject: (a: ActionProposal) => void
  onModify: (a: ActionProposal, note: string) => void
  icsUrl: (a: ActionProposal) => string | null
}

function download(name: string, text: string, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Human-in-the-Loop approval cards: Approve / Modify / Reject, then the Action Receipt. */
export function ActionCards({ actions, onApprove, onReject, onModify, icsUrl }: Props) {
  const visible = actions.filter((a) => !(a.receipt as any)?.superseded)
  const superseded = actions.length - visible.length
  return (
    <section className="panel flex h-full flex-col p-4" id="hitl-actions">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="panel-title"><Bot size={13} /> Actor · human-in-the-loop</h3>
        {superseded > 0 && <span className="chip text-pink-200">{superseded} superseded by re-plan</span>}
      </header>
      <div className="scroll-thin flex-1 space-y-2 overflow-auto pr-1">
        {visible.length === 0 && <div className="py-6 text-center text-xs text-slate-500">Proposed actions appear here for your approval.</div>}
        <AnimatePresence initial={false}>
          {visible.map((a) => (
            <ActionCard key={a.id} a={a} onApprove={onApprove} onReject={onReject} onModify={onModify} icsUrl={icsUrl} />
          ))}
        </AnimatePresence>
      </div>
    </section>
  )
}

function ActionCard({ a, onApprove, onReject, onModify, icsUrl }: { a: ActionProposal } & Omit<Props, 'actions'>) {
  const [editing, setEditing] = useState(false)
  const [note, setNote] = useState('')
  const Icon = TYPE_ICON[a.type] || Bot
  const open = a.status === 'pending' || a.status === 'modified'
  const busy = a.status === 'approved'
  const r: any = a.receipt
  return (
    <motion.article layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
      className={cn('rounded-xl border p-3', a.status === 'executed' ? 'border-emerald-400/25 bg-emerald-400/[0.04]' : a.status === 'rejected' ? 'border-white/5 opacity-50' : 'border-white/10 bg-white/[0.025]')}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-emerald-400/10 text-emerald-300"><Icon size={14} /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <h4 className="text-[12.5px] font-semibold text-slate-100">{a.title}</h4>
            <span className={cn('chip', RISK[a.risk])}>{a.risk} risk</span>
            {a.requires_approval ? <span className="chip">approval required</span> : <span className="chip">auto</span>}
            <span className="chip font-mono">{a.status}</span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-400">{a.description}</p>
        </div>
      </div>

      {open && a.requires_approval && (
        <div className="mt-2">
          {editing ? (
            <div className="flex gap-1.5">
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. 2 adults, aisle seat, flexible refund"
                className="flex-1 rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-[11px] outline-none focus:border-violet-400/50" />
              <button className="btn-ghost" onClick={() => { if (note.trim()) onModify(a, note.trim()); setEditing(false); setNote('') }}>Save</button>
            </div>
          ) : (
            <div className="flex gap-1.5">
              <button className="btn-ok" onClick={() => onApprove(a)}><CheckCircle2 size={13} /> Approve</button>
              <button className="btn-ghost" onClick={() => setEditing(true)}><Pencil size={12} /> Modify</button>
              <button className="btn-bad" onClick={() => onReject(a)}><XCircle size={12} /> Reject</button>
            </div>
          )}
        </div>
      )}
      {open && !a.requires_approval && (
        <button className="btn-ghost mt-2" onClick={() => onApprove(a)}><CheckCircle2 size={12} /> Run</button>
      )}
      {busy && <div className="mt-2 flex items-center gap-1.5 text-[11px] text-cyan-300"><Loader2 size={12} className="animate-spin" /> Executing…</div>}

      {a.status === 'executed' && r && <Receipt a={a} r={r} icsUrl={icsUrl} />}
      {a.status === 'failed' && <p className="mt-2 text-[11px] text-rose-300">Failed: {r?.error}</p>}
    </motion.article>
  )
}

function Receipt({ a, r, icsUrl }: { a: ActionProposal; r: any; icsUrl: Props['icsUrl'] }) {
  const ics = icsUrl(a)
  return (
    <div className="mt-2 rounded-lg border border-emerald-400/20 bg-black/30 p-2 text-[10.5px] text-slate-300">
      <div className="mb-1 flex items-center gap-1 font-semibold text-emerald-300"><CheckCircle2 size={11} /> Action receipt{r.confirmation ? ` · ${r.confirmation}` : ''}</div>
      {r.browser && (
        <div className="space-y-0.5">
          <div className="text-slate-400">Browser: <span className="font-mono text-slate-200">{r.browser.engine}</span>{r.browser.reason ? ` (${r.browser.reason})` : ''}{r.browser.page_title ? ` · ${r.browser.page_title}` : ''}</div>
          {(r.browser.steps || []).map((st: any) => (
            <div key={st.step} className="font-mono text-[10px] text-slate-400">{st.step}. {st.action} — <span className={st.status === 'done' ? 'text-emerald-300' : 'text-amber-300'}>{st.status}</span></div>
          ))}
          {r.browser.screenshot && <img src={r.browser.screenshot} alt="Playwright evidence screenshot" className="mt-1 max-h-40 rounded border border-white/10" />}
        </div>
      )}
      {r.cover_note && <pre className="mt-1 whitespace-pre-wrap rounded bg-white/[0.03] p-1.5 font-sans text-[10.5px]">{r.cover_note}</pre>}
      {r.ics && (
        ics ? <a className="btn-ghost mt-1" href={ics}><Download size={11} /> Download .ics</a>
            : <button className="btn-ghost mt-1" onClick={() => download(r.filename || 'compass.ics', r.ics, 'text/calendar')}><Download size={11} /> Download .ics</button>
      )}
      {r.markdown && <button className="btn-ghost mt-1" onClick={() => download('compass-report.md', r.markdown, 'text/markdown')}><Download size={11} /> Download report (.md)</button>}
      {r.drafts && (
        <details className="mt-1"><summary className="cursor-pointer text-slate-400">{r.drafts.length} RFQ draft(s)</summary>
          {r.drafts.map((d: any, i: number) => <pre key={i} className="mt-1 whitespace-pre-wrap rounded bg-white/[0.03] p-1.5 font-sans">{d.subject}{'\n\n'}{d.body}</pre>)}
        </details>
      )}
      {r.watch && <div>Watch <span className="font-mono">{r.watch.id}</span> · {r.watch.label} · every {r.watch.cadence_minutes} min · ±{r.watch.threshold_pct}%</div>}
      {r.delivery && (
        <div className="mt-1 flex flex-wrap gap-1">
          {(Array.isArray(r.delivery) ? r.delivery : [r.delivery]).map((d: any, i: number) => (
            <span key={i} className={cn('chip', d.sent ? 'text-emerald-300' : 'text-slate-400')} title={d.reason || ''}>{d.channel}: {d.sent ? 'sent' : 'not configured'}</span>
          ))}
        </div>
      )}
      {r.offline && <div className="text-slate-500">Offline demo receipt (no backend).</div>}
    </div>
  )
}
