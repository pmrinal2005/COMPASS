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

export interface VenuePlatform { title: string; rating?: number | null; reviews?: number | null; price_level?: number | null; url?: string | null }
export interface VenueInsight {
  id: string; title: string; rating?: number | null; reviews?: number | null; verified: boolean; anomaly?: string | null
  price_level?: number | null; spread?: number; meets_filters?: boolean; platforms: Record<string, VenuePlatform>; score?: number
}
export interface EventInsight { title: string; when?: string | null; venue?: string | null; url?: string | null; tickets?: string[] }
export interface SeoGridCell { engine: string; label: string; weight: number; position: number | null; found: boolean; ctr: number; leader?: string | null; leader_pos?: number | null }
export type Insights =
  | { kind: 'venues'; city?: string; query?: string; platforms: string[]; yelp_supported: boolean; min_rating?: number; price_cap?: number; venues: VenueInsight[]; events: EventInsight[] }
  | {
      kind: 'seo'; domain?: string; keyword?: string; market?: string; grid: SeoGridCell[]; ai: { engine: string; label: string; cited: boolean }[]
      rank_of: number | null; total_domains: number; visibility: number; share_of_voice: number; coverage: number; avg_position: number | null
      anomaly?: string | null; leaders: { domain: string; visibility: number; found: number }[]; ai_text?: Record<string, string>
    }
  | { kind: 'trip'; events: EventInsight[]; stays: { title: string; price?: number | null; rating?: number | null; reviews?: number | null; url?: string | null; verified: boolean; qualifier?: string }[] }

export interface Playbook {
  id: string; name: string; ecosystem: string; lens: Lens; description: string; keywords: string[]; examples: string[]
  engine_list: string[]; fallback_engine_list: string[]; dimensions: Record<string, { weight: number; direction: 'min' | 'max'; label: string }>; actions: string[]
}

export interface Account {
  demo: boolean; account_status?: string; plan_name?: string; plan_monthly_price?: number | null; plan_renewal_date?: string | null
  searches_per_month?: number; plan_searches_left?: number; extra_credits?: number; total_searches_left?: number; this_month_usage?: number
  this_hour_searches?: number; last_hour_searches?: number; account_rate_limit_per_hour?: number
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
  insights?: Insights | null
  prevInsights?: Insights | null
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
  rehydrated?: boolean
  error?: string
  events: CompassEvent[]
  round: number
}
