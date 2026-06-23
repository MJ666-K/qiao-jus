import { apiClient } from './client'

export interface ChunkItem {
  id: string
  document_id: string
  parent_id: string | null
  chunk_index: number
  text: string
  token_count: number | null
  char_count: number | null
  scope: string
  metadata: Record<string, unknown>
}

export async function listChunks(documentId: string): Promise<ChunkItem[]> {
  const { data } = await apiClient.get<ChunkItem[]>(`/documents/${documentId}/chunks`)
  return data
}

export async function updateChunk(
  documentId: string,
  chunkId: string,
  text: string,
  reEmbed = true,
): Promise<ChunkItem> {
  const { data } = await apiClient.put<ChunkItem>(
    `/documents/${documentId}/chunks/${chunkId}`,
    { text, re_embed: reEmbed },
  )
  return data
}

export async function deleteChunk(documentId: string, chunkId: string): Promise<void> {
  await apiClient.delete(`/documents/${documentId}/chunks/${chunkId}`)
}
