import { apiClient } from './client'
import type { DocumentItem, DocumentListResult } from '@/types'

export async function listDocuments(params?: {
  dataset_id?: string
  status_filter?: string
  doc_type?: string
  uploaded_only?: boolean
  page?: number
  page_size?: number
}): Promise<DocumentListResult> {
  const { data } = await apiClient.get<DocumentListResult>('/documents', { params })
  return data
}

/** 分页拉取全部文档（后端 page_size 上限 100） */
export async function listAllDocuments(
  params?: Omit<NonNullable<Parameters<typeof listDocuments>[0]>, 'page' | 'page_size'>,
): Promise<DocumentItem[]> {
  const pageSize = 100
  const items: DocumentItem[] = []
  let page = 1
  let total = 0
  do {
    const res = await listDocuments({ ...params, page, page_size: pageSize })
    items.push(...res.items)
    total = res.total
    page += 1
  } while (items.length < total)
  return items
}

export async function getDocument(id: string): Promise<DocumentItem> {
  const { data } = await apiClient.get<DocumentItem>(`/documents/${id}`)
  return data
}

export async function uploadDocument(
  file: File,
  datasetId: string,
  docType = 'default',
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
