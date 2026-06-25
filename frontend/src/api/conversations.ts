import { apiClient } from './client'
import type { Conversation, ConversationCreate, ConversationSummary } from '@/types'

export async function listConversations(assistantId: string): Promise<ConversationSummary[]> {
  const res = await apiClient.get<ConversationSummary[]>('/conversations', {
    params: { assistant_id: assistantId },
  })
  return res.data
}

export async function getConversation(id: string): Promise<Conversation> {
  const res = await apiClient.get<Conversation>(`/conversations/${id}`)
  return res.data
}

export async function createConversation(payload: ConversationCreate): Promise<Conversation> {
  const res = await apiClient.post<Conversation>('/conversations', payload)
  return res.data
}

export async function updateConversation(id: string, payload: Partial<ConversationCreate>): Promise<Conversation> {
  const res = await apiClient.patch<Conversation>(`/conversations/${id}`, payload)
  return res.data
}

export async function deleteConversation(id: string): Promise<void> {
  await apiClient.delete(`/conversations/${id}`)
}
