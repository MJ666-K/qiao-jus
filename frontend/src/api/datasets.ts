import { apiClient } from './client'
import type { Dataset } from '@/types'

export async function listDatasets(): Promise<Dataset[]> {
  const { data } = await apiClient.get<Dataset[]>('/datasets')
  return data
}

export async function createDataset(payload: {
  name: string
  description?: string | null
  metadata?: Record<string, unknown>
}): Promise<Dataset> {
  const { data } = await apiClient.post<Dataset>('/datasets', payload)
  return data
}

export async function deleteDataset(id: string): Promise<void> {
  await apiClient.delete(`/datasets/${id}`)
}

export async function updateDataset(
  id: string,
  payload: { name?: string; description?: string | null },
): Promise<Dataset> {
  const { data } = await apiClient.patch<Dataset>(`/datasets/${id}`, payload)
  return data
}
