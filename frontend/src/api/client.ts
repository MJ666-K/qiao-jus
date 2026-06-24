import axios, { type AxiosError } from 'axios'
import type { Token } from '@/types'

const TOKEN_KEY = 'ks_token'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 120_000,
})

apiClient.interceptors.request.use((config) => {
  const tokenData = getTokenData()
  if (tokenData?.access_token) {
    config.headers.Authorization = `Bearer ${tokenData.access_token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status
    
    if (status === 401) {
      const tokenData = getTokenData()
      if (tokenData?.refresh_token) {
        try {
          const newToken = await refreshToken(tokenData.refresh_token)
          setTokenData(newToken)
          const originalRequest = error.config!
          originalRequest.headers.Authorization = `Bearer ${newToken.access_token}`
          return apiClient.request(originalRequest)
        } catch {
          clearTokenData()
        }
      } else {
        clearTokenData()
      }
    }
    
    let message =
      error.response?.data?.detail ||
      error.message ||
      '请求失败'
    if (status === 500 && !error.response?.data?.detail) {
      message = '后端服务未就绪（可能未启动或正在初始化），请执行 knowledge-service/scripts/start.sh 后重试'
    } else if (!error.response) {
      message = '无法连接后端 API，请确认 knowledge-service 已启动（端口 8000）'
    }
    return Promise.reject(new Error(typeof message === 'string' ? message : JSON.stringify(message)))
  },
)

export function getTokenData(): Token | null {
  const raw = localStorage.getItem(TOKEN_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Token
  } catch {
    return null
  }
}

export function getToken(): string | null {
  const data = getTokenData()
  return data?.access_token || null
}

export function setTokenData(token: Token): void {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(token))
}

export function setToken(token: string): void {
  const existing = getTokenData()
  setTokenData({
    access_token: token,
    refresh_token: existing?.refresh_token || '',
  })
}

export function clearTokenData(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function clearToken(): void {
  clearTokenData()
}

async function refreshToken(refreshToken: string): Promise<Token> {
  const { data } = await axios.post<Token>(
    (import.meta.env.VITE_API_BASE || '/api') + '/auth/refresh',
    { refresh_token: refreshToken },
    { timeout: 10000 }
  )
  return data
}
