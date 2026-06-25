import { apiClient } from './client'
import type { Community, GlobalAnswerResult, GraphEdge, GraphNode, GraphQueryResult } from '@/types'

function normalizeGraphResult(raw: unknown): GraphQueryResult {
  if (!raw || typeof raw !== 'object') {
    return { entities: [], relations: [], related_chunks: [] }
  }
  const top = raw as Record<string, unknown>
  const payload =
    Array.isArray(top.entities) ? top : (top.data as Record<string, unknown> | undefined) ?? top
  return {
    entities: Array.isArray(payload.entities) ? (payload.entities as GraphNode[]) : [],
    relations: Array.isArray(payload.relations) ? (payload.relations as GraphEdge[]) : [],
    related_chunks: Array.isArray(payload.related_chunks) ? payload.related_chunks : [],
  }
}

export async function fetchGraphStats(): Promise<{ entity_count: number }> {
  const { data } = await apiClient.get<{ entity_count: number }>('/graph/stats')
  return data
}

export async function localGraph(payload: {
  query: string
  depth?: number
  dataset_id?: string
}): Promise<GraphQueryResult> {
  const { data } = await apiClient.post<GraphQueryResult>('/graph/local', payload)
  return normalizeGraphResult(data)
}

export async function listCommunities(level = 0): Promise<Community[]> {
  const { data } = await apiClient.get<Community[]>('/graph/communities', { params: { level } })
  return data
}

export async function rebuildCommunities(): Promise<{
  status: string
  communities?: number
  entities_covered?: number
}> {
  const { data } = await apiClient.post('/graph/rebuild')
  return data
}

export async function createGraphRelation(payload: {
  source: string
  target: string
  type?: string
  description?: string
}): Promise<GraphQueryResult['relations'][0]> {
  const { data } = await apiClient.post('/graph/relations', payload)
  return data
}

export async function deleteGraphRelation(source: string, target: string): Promise<void> {
  await apiClient.delete('/graph/relations', { params: { source, target } })
}

export async function globalAnswer(payload: {
  query: string
  depth?: number
}): Promise<GlobalAnswerResult> {
  const { data } = await apiClient.post<GlobalAnswerResult>('/graph/global', payload)
  return data
}
