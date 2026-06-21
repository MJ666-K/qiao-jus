import { apiClient } from './client'
import type { Community, GlobalAnswerResult, GraphQueryResult } from '@/types'

export async function localGraph(payload: {
  query: string
  depth?: number
}): Promise<GraphQueryResult> {
  const { data } = await apiClient.post<GraphQueryResult>('/graph/local', payload)
  return data
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

export async function globalAnswer(payload: {
  query: string
  depth?: number
}): Promise<GlobalAnswerResult> {
  const { data } = await apiClient.post<GlobalAnswerResult>('/graph/global', payload)
  return data
}
