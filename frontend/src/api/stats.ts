import { apiClient } from './client'
import type { Stats } from '@/types'

export async function fetchStats(): Promise<Stats> {
  const { data } = await apiClient.get<Stats>('/stats')
  return data
}
