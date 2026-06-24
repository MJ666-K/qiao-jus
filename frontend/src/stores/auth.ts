import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMe, login as apiLogin, register as apiRegister } from '@/api/auth'
import { clearTokenData, getTokenData, setTokenData } from '@/api/client'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)
  const ready = ref(false)

  async function login(email: string, password: string, captchaKey: string, captchaCode: string) {
    loading.value = true
    try {
      const token = await apiLogin(email, password, captchaKey, captchaCode)
      setTokenData(token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  async function register(
    email: string,
    password: string,
    tenantName: string,
    captchaKey: string,
    captchaCode: string,
  ) {
    loading.value = true
    try {
      const token = await apiRegister(email, password, tenantName, captchaKey, captchaCode)
      setTokenData(token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  async function restore() {
    if (ready.value) return
    const tokenData = getTokenData()
    if (!tokenData?.access_token) {
      ready.value = true
      return
    }
    try {
      user.value = await fetchMe()
      if (!user.value?.id || !user.value?.tenant_id) {
        throw new Error('invalid user profile')
      }
    } catch {
      clearTokenData()
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function ensureUser() {
    if (user.value) return user.value
    const tokenData = getTokenData()
    if (!tokenData?.access_token) return null
    await restore()
    return user.value
  }

  function logout() {
    clearTokenData()
    user.value = null
  }

  return { user, loading, ready, login, register, restore, ensureUser, logout }
})
