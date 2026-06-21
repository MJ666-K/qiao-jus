import { apiClient } from './client'
import type { Token, User } from '@/types'

type MePayload = User | { user?: User | null }

function normalizeUser(raw: Record<string, unknown>): User {
  return {
    id: String(raw.id ?? ''),
    tenant_id: String(raw.tenant_id ?? ''),
    email: String(raw.email ?? ''),
    scopes: Array.isArray(raw.scopes) ? (raw.scopes as string[]) : [],
  }
}

export async function login(email: string, password: string): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/login', { email, password })
  return data
}

export async function register(
  email: string,
  password: string,
  tenantName: string,
): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/register', {
    email,
    password,
    tenant_name: tenantName,
  })
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get<MePayload>('/auth/me')
  if (data && typeof data === 'object' && 'user' in data && data.user) {
    return normalizeUser(data.user as unknown as Record<string, unknown>)
  }
  return normalizeUser(data as unknown as Record<string, unknown>)
}
