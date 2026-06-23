import { apiClient } from './client'
import type { Token, User } from '@/types'

function normalizeUser(raw: Record<string, unknown>): User {
  return {
    id: String(raw.id ?? ''),
    tenant_id: String(raw.tenant_id ?? ''),
    email: String(raw.email ?? ''),
    role: String(raw.role ?? 'user'),
    display_name: (raw.display_name as string | null) ?? null,
    scopes: Array.isArray(raw.scopes) ? (raw.scopes as string[]) : [],
  }
}

export interface Captcha {
  captcha_key: string
  image: string
}

export async function getCaptcha(): Promise<Captcha> {
  const { data } = await apiClient.get<Captcha>('/auth/captcha')
  return data
}

export async function login(
  email: string,
  password: string,
  captchaKey: string,
  captchaCode: string,
): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/login', {
    email,
    password,
    captcha_key: captchaKey,
    captcha_code: captchaCode,
  })
  return data
}

export async function register(
  email: string,
  password: string,
  tenantName: string,
  captchaKey: string,
  captchaCode: string,
): Promise<Token> {
  const { data } = await apiClient.post<Token>('/auth/register', {
    email,
    password,
    tenant_name: tenantName,
    captcha_key: captchaKey,
    captcha_code: captchaCode,
  })
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get('/auth/me')
  return normalizeUser(data as Record<string, unknown>)
}

export async function listUsers(): Promise<User[]> {
  const { data } = await apiClient.get('/admin/users')
  return (data as Record<string, unknown>[]).map(normalizeUser)
}

export async function updateUserRole(
  userId: string,
  payload: { role?: string; display_name?: string },
): Promise<User> {
  const { data } = await apiClient.patch(`/admin/users/${userId}`, payload)
  return normalizeUser(data as Record<string, unknown>)
}
