import { apiClient } from './client'
import type { Assistant, AssistantCreate, AssistantSummary } from '@/types'

export async function listAssistants(): Promise<AssistantSummary[]> {
  const res = await apiClient.get<AssistantSummary[]>('/assistants')
  return res.data
}

export async function getAssistant(id: string): Promise<Assistant> {
  const res = await apiClient.get<Assistant>(`/assistants/${id}`)
  return res.data
}

export async function createAssistant(payload: AssistantCreate): Promise<Assistant> {
  const res = await apiClient.post<Assistant>('/assistants', payload)
  return res.data
}

export async function updateAssistant(
  id: string,
  payload: Partial<AssistantCreate>,
): Promise<Assistant> {
  const res = await apiClient.patch<Assistant>(`/assistants/${id}`, payload)
  return res.data
}

export async function deleteAssistant(id: string): Promise<void> {
  await apiClient.delete(`/assistants/${id}`)
}
