export type Lens = 'go' | 'pro'
export type AgentName = 'orchestrator' | 'researcher' | 'analyst' | 'actor'
export type AgentStatus = 'idle' | 'active' | 'done'

export interface CompassEvent {
  seq: number
  ts: number
  type: string
  agent?: string | null
  data: any
}

export interface EngineCall {
  id: string
  engine: string
  params: Record<string, any>
  purpose: string
  category: string
  essential: boolean
}

export interface DecisionNode {
  id: string
  kind: 'entity' | 'dimension' | 'constraint' | 'source' | 'action'
  label: string
  meta: Record<string, any>
}

export interface DecisionGraph {
  playbook_id: string
  intent: string
  lens: Lens
  slots: Record<string, any>
  nodes: DecisionNode[]
  calls: EngineCall[]
  weights: Record<string, number>
}

export interface CallState {
  id: string
  engine: string
  params: Record<string, any>
  purpose: string
  status: 'pending' | 'inflight' | 'done' | 'cached' | 'error'
  ms?: number
  results?: number
  round: number
  error?: string
}

export interface LogEntry {
  seq: number
  ts: number
  kind: 'request' | 'response' | 'cached' | 'error'
  callId: string
  engine: string
  params?: Record<string, any>
  purpose?: string
  ms?: number
  results?: number
  status?: string
  mode?: string
  searchId?: string
  raw?: any
  error?: string
}

export interface MatrixRow {
  id: string
  title: string
  category: string
  engine: string
  source: string
  url?: string | null
  price?: number | null
  rating?: number | null
  reviews?: number | null
  score: number
  breakdown: Record<string, number>
  raw?: Record<string, any>
  verified: boolean
  sources: string[]
  anomaly?: string | null
  attributes: Record<string, any>
}

export interface Matrix {
  dimensions: { key: string; label: string; weight: number; direction: 'min' | 'max' }[]
  rows: MatrixRow[]
}

export interface ActionProposal {
  id: string
  session_id: string
  type: string
  title: string
  description: string
  payload: Record<string, any>
  risk: 'low' | 'medium' | 'high'
  requires_approval: boolean
  status: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed' | 'modified'
  receipt?: Record<string, any> | null
  created_at: number
}

export interface ReplanEntry {
  iteration: number
  confidence: number
  reasons: string[]
  new_calls: { engine: string; purpose: string }[]
  max?: number
}

export interface RagHit {
  title: string
  engine: string
  rrf: number
  dense_rank?: number | null
  keyword_rank?: number | null
  similarity?: number
  candidate_id?: string
}

export interface Credits {
  budget: number
  spent: number
  remaining: number
  cached: number
}

export interface SessionState {
  sessionId: string | null
  prompt: string
  lens: Lens
  status: 'idle' | 'connecting' | 'running' | 'awaiting_budget' | 'done' | 'error'
  stage: string
  replay: boolean
  agents: Record<AgentName, AgentStatus>
  agentLabel: Partial<Record<AgentName, string>>
  intent?: { playbook_id: string; playbook: string; scores: any[] }
  graph?: DecisionGraph
  calls: Record<string, CallState>
  callOrder: string[]
  logs: LogEntry[]
  rag?: { indexed: number; backend: string; embedder: string; hits: RagHit[] }
  verification?: { total: number; verified: number; ratio: number; flagged: any[] }
  matrix?: Matrix
  prevOrder: string[]
  confidence?: number
  threshold?: number
  reasons: string[]
  rationale?: string
  context?: Record<string, any>
  anomalies: any[]
  replans: ReplanEntry[]
  actions: Record<string, ActionProposal>
  actionOrder: string[]
  credits?: Credits
  caveat?: string | null
  budgetPrompt?: { calls: number; essential: number; credits: Credits } | null
  disruption?: any
  watches: any[]
  watchTicks: any[]
  error?: string
  events: CompassEvent[]
  round: number
}
