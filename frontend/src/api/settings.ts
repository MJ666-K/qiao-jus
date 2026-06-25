import { apiClient } from './client'

export interface RuntimeConfig {
  chunk_parent_tokens: number
  chunk_child_tokens: number
  chunk_overlap_tokens: number
  search_top_k: number
  rrf_k: number
  rerank_top_k: number
  bm25_k1: number
  bm25_b: number
  dense_top_k_multiplier: number
  rerank_model_id: string
  rerank_instruct: string
  llm_max_tokens: number
  llm_chat_temperature: number
  llm_stream_temperature: number
  llm_json_temperature: number
  llm_suggest_temperature: number
}

/** @deprecated use RuntimeConfig */
export type ChunkingConfig = RuntimeConfig

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  const { data } = await apiClient.get<RuntimeConfig>('/settings/runtime')
  return data
}

export async function updateRuntimeConfig(cfg: RuntimeConfig): Promise<RuntimeConfig> {
  const { data } = await apiClient.put<RuntimeConfig>('/settings/runtime', cfg)
  return data
}

export async function getChunkingConfig(): Promise<RuntimeConfig> {
  return getRuntimeConfig()
}

export async function updateChunkingConfig(cfg: RuntimeConfig): Promise<RuntimeConfig> {
  return updateRuntimeConfig(cfg)
}
