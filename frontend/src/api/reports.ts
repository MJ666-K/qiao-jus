import { apiClient } from './client'
import type { AnalyzeRequest, Report } from '@/types'

export async function listReports(): Promise<Report[]> {
  const res = await apiClient.get<Report[]>('/reports')
  return res.data
}

export async function getReport(id: string): Promise<Report> {
  const res = await apiClient.get<Report>(`/reports/${id}`)
  return res.data
}

export async function analyzeReport(payload: AnalyzeRequest): Promise<Report> {
  const res = await apiClient.post<Report>('/analyze', payload)
  return res.data
}
