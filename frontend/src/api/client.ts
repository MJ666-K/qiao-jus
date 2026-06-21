import axios, { type AxiosError } from 'axios'

const TOKEN_KEY = 'ks_token'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 120_000,
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status
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

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}
