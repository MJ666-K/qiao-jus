import { apiClient } from './client'
import type { DocumentItem } from '@/types'

export async function listDocuments(params?: {
  dataset_id?: string
  status_filter?: string
  doc_type?: string
}): Promise<DocumentItem[]> {
  const { data } = await apiClient.get<DocumentItem[]>('/documents', { params })
  return data
}

export async function getDocument(id: string): Promise<DocumentItem> {
  const { data } = await apiClient.get<DocumentItem>(`/documents/${id}`)
  return data
}

export async function uploadDocument(
  file: File,
  datasetId: string,
  docType = 'general',
): Promise<DocumentItem> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<DocumentItem>(
    `/documents/upload?dataset_id=${datasetId}&doc_type=${docType}`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return data
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/documents/${id}`)
}

export async function reindexDocument(id: string): Promise<{ status: string; message: string }> {
  const { data } = await apiClient.post(`/documents/${id}/reindex`)
  return data
}
