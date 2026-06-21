import { apiClient } from './client'
import type { Token, User } from '@/types'

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
  const { data } = await apiClient.get<User>('/auth/me')
  return data
}
