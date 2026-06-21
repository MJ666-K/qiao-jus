export interface Token {
  access_token: string
  refresh_token: string
}

export interface User {
  id: string
  tenant_id: string
  email: string
  scopes: string[]
}

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
  title: string
  source_uri: string | null
  mime_type: string | null
  content_hash: string | null
  status: string
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
