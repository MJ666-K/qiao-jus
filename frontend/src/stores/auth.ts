import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMe, login as apiLogin, register as apiRegister } from '@/api/auth'
import { clearToken, setToken } from '@/api/client'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)
  const ready = ref(false)

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const token = await apiLogin(email, password)
      setToken(token.access_token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  async function register(email: string, password: string, tenantName: string) {
    loading.value = true
    try {
      const token = await apiRegister(email, password, tenantName)
      setToken(token.access_token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  async function restore() {
    if (ready.value) return
    const token = localStorage.getItem('ks_token')
    if (!token) {
      ready.value = true
      return
    }
    try {
      user.value = await fetchMe()
      if (!user.value?.id || !user.value?.tenant_id) {
        throw new Error('invalid user profile')
      }
    } catch {
      clearToken()
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function ensureUser() {
    if (user.value) return user.value
    if (!localStorage.getItem('ks_token')) return null
    await restore()
    return user.value
  }

  function logout() {
    clearToken()
    user.value = null
  }

  return { user, loading, ready, login, register, restore, ensureUser, logout }
})
