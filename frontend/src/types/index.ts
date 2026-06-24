export interface Token {
  access_token: string
  refresh_token: string
}

export interface User {
  id: string
  tenant_id: string
  email: string
  role: string
  display_name?: string | null
  scopes: string[]
}

export type UserRole = 'user' | 'admin'

export interface Dataset {
  id: string
  tenant_id: string
  name: string
  description: string | null
  acl: Record<string, unknown> | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface DocumentItem {
  id: string
  dataset_id: string
  user_id?: string | null
  title: string
  source_uri: string | null
  mime_type: string | null
  content_hash: string | null
  status: string
  scope?: string
  error: string | null
  acl: Record<string, unknown> | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string | null
}

export interface SearchHit {
  chunk_id: string
  text: string
  score: number
  source: string | null
  document_id: string | null
  page: number | null
  metadata: Record<string, unknown>
  doc_type?: string | null
  article_no?: string | null
  law_name?: string | null
}

export interface SearchResult {
  query: string
  hits: SearchHit[]
  graph_context: Array<{ name?: string; type?: string }>
}

export interface AnswerResult {
  query: string
  answer: string
  sources: SearchHit[]
  graph_entities: string[]
}

export interface GraphNode {
  id: string
  name: string
  type: string
  description?: string | null
}

export interface GraphEdge {
  source: string
  target: string
  type?: string
  description?: string | null
  weight?: number
}

export interface GraphQueryResult {
  entities: GraphNode[]
  relations: GraphEdge[]
  related_chunks: unknown[]
}

export interface Community {
  id: string
  title: string | null
  summary: string | null
  level: number
}

export interface GlobalAnswerResult {
  answer: string
  communities_used?: number
  community_refs?: Array<{
    title?: string
    partial_excerpt?: string
  }>
}

export interface Stats {
  datasets: number
  documents: number
  documents_done: number
  chunks: number
  qdrant_points: number
  job_breakdown: Array<{ stage: string; status: string; count: number }>
}

export type DocStatus =
  | 'pending'
  | 'parsing'
  | 'chunking'
  | 'embedding'
  | 'graphing'
  | 'done'
  | 'failed'

export type ReportType =
  | 'contract_review'
  | 'dispute_analysis'
  | 'labor_risk'
  | 'litigation_draft'
  | 'evidence_checklist'

export type ReportStatus = 'pending' | 'generating' | 'done' | 'failed'

export type SourceType = 'law' | 'case' | 'report' | 'user_doc' | 'compliance' | 'graph'

export interface Citation {
  chunk_id?: string | null
  document_id?: string | null
  source_type: SourceType
  source_title: string
  excerpt?: string | null
  page?: number | null
  score?: number | null
}

export interface RiskItem {
  level: '高' | '中' | '低'
  desc: string
  law_ref?: string | null
  chunk_id?: string | null
  suggestion?: string | null
}

export interface EvidenceItem {
  name: string
  level: '高' | '中' | '低'
  purpose?: string | null
  collect_tip?: string | null
}

export interface LitigationParties {
  plaintiff?: string | null
  defendant?: string | null
}

export interface Report {
  id: string
  tenant_id: string
  user_id: string
  source_doc_id?: string | null
  type: ReportType
  status: ReportStatus
  error?: string | null
  summary?: string | null
  risk_items: RiskItem[]
  citations: Citation[]
  suggested_questions: string[]
  confidence: number
  graph_path: string[]
  parties?: LitigationParties | null
  claims?: string[]
  facts?: string[]
  evidence_list?: Array<{ name?: string; purpose?: string }>
  evidence_items?: EvidenceItem[]
  procedure_steps?: string[]
  content_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AnalyzeRequest {
  source_doc_id?: string
  text?: string
  title?: string
  report_type?: ReportType
  extra_context?: string
}

export interface ConversationSummary {
  id: string
  title: string
  report_id?: string | null
  track?: string | null
  message_count: number
  enable_thinking: boolean
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  confidence?: number | null
  suggested_questions: string[]
  citations: Citation[]
  created_at: string
}

export interface Conversation {
  id: string
  tenant_id: string
  user_id: string
  report_id?: string | null
  title: string
  track?: string | null
  enable_thinking: boolean
  created_at: string
  updated_at: string
  messages: ChatMessage[]
}

export interface ConversationCreate {
  title?: string
  report_id?: string
  track?: string
  enable_thinking?: boolean
}

export type WsClientMessage =
  | { type: 'init'; conversation_id?: string; report_id?: string }
  | { type: 'message'; content: string }
  | { type: 'bind_report'; report_id?: string }
  | { type: 'stop' }

export type WsServerMessage =
  | { type: 'connected'; session_id: string; report_id?: string | null }
  | { type: 'status'; content: string }
  | { type: 'token'; content: string }
  | { type: 'citation'; chunk_id?: string; document_id?: string; source_type: SourceType; source_title: string; excerpt?: string; page?: number }
  | { type: 'done'; message_id: string; content?: string; confidence: number; citations: Citation[]; suggested_questions: string[] }
  | { type: 'report_bound'; report_id?: string | null }
  | { type: 'error'; message: string }
