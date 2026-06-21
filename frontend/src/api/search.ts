import { apiClient } from './client'
import type { AnswerResult, SearchResult } from '@/types'

export async function search(payload: {
  query: string
  top_k?: number
  dataset_id?: string
  use_graph?: boolean
}): Promise<SearchResult> {
  const { data } = await apiClient.post<SearchResult>('/search', payload)
  return data
}

export async function answer(payload: {
  query: string
  top_k?: number
  dataset_id?: string
  use_graph?: boolean
}): Promise<AnswerResult> {
  const { data } = await apiClient.post<AnswerResult>('/search/answer', payload)
  return data
}
