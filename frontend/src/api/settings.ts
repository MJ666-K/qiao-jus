import { apiClient } from './client'

export interface ChunkingConfig {
  chunk_parent_tokens: number
  chunk_child_tokens: number
  chunk_overlap_tokens: number
  search_top_k: number
  rrf_k: number
  rerank_top_k: number
  bm25_k1: number
  bm25_b: number
  dense_top_k_multiplier: number
}

export async function getChunkingConfig(): Promise<ChunkingConfig> {
  const { data } = await apiClient.get<ChunkingConfig>('/settings/chunking')
  return data
}

export async function updateChunkingConfig(cfg: ChunkingConfig): Promise<ChunkingConfig> {
  const { data } = await apiClient.put<ChunkingConfig>('/settings/chunking', cfg)
  return data
}
