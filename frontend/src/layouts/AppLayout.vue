<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  Collection,
  DataAnalysis,
  DocumentCopy,
  Files,
  Grid,
  Search,
  Setting,
  Share,
  SwitchButton,
  Tools,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

interface NavItem {
  path: string
  label: string
  icon: typeof Grid
  exact?: boolean
  adminOnly?: boolean
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const allNavItems: NavItem[] = [
  { path: '/dashboard', label: '概览', icon: DataAnalysis },
  { path: '/documents', label: '我的文档', icon: Files },
  { path: '/reports/new', label: '生成报告', icon: Tools, exact: true },
  { path: '/reports', label: '我的报告', icon: DocumentCopy },
  { path: '/chat', label: '智能问答', icon: ChatDotRound },
  { path: '/datasets', label: '平台知识库', icon: Collection, adminOnly: true },
  { path: '/search', label: '检索测试', icon: Search, adminOnly: true },
  { path: '/graph', label: '知识图谱', icon: Share, adminOnly: true },
  { path: '/settings', label: '系统配置', icon: Setting },
]

const visibleNavItems = computed(() =>
  allNavItems.filter((item) => !item.adminOnly || auth.user?.role === 'admin'),
)

const isAdmin = computed(() => auth.user?.role === 'admin')
const roleLabel = computed(() => (isAdmin.value ? '管理员' : '普通用户'))
const roleTagType = computed(() => (isAdmin.value ? 'danger' : 'primary'))

function isActive(item: NavItem): boolean {
  if (item.exact) {
    return route.path === item.path
  }
  if (item.path === '/reports') {
    return route.path.startsWith('/reports') && !route.path.startsWith('/reports/new')
  }
  return route.path.startsWith(item.path) && route.path.length >= item.path.length
}

const avatarText = computed(() => {
  const name = auth.user?.display_name || auth.user?.email
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
})

const displayName = computed(() => auth.user?.display_name || auth.user?.email?.split('@')[0] || '—')

function goSettings() {
  router.push('/settings')
}

function handleUserCommand(cmd: string) {
  if (cmd === 'settings') goSettings()
  else if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}

onMounted(async () => {
  if (!auth.user && localStorage.getItem('ks_token')) {
    await auth.ensureUser()
  }
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">枫</div>
        <div>
          <div class="brand-title">枫桥智诉</div>
          <div class="brand-sub">法律智能辅助平台</div>
        </div>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in visibleNavItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <el-dropdown v-if="auth.user" trigger="click" placement="top-start" @command="handleUserCommand">
          <div class="user-trigger">
            <el-avatar :size="36" class="user-avatar">{{ avatarText }}</el-avatar>
            <div class="user-info">
              <span class="user-email">{{ displayName }}</span>
              <el-tag :type="roleTagType" size="small" effect="dark" round>{{ roleLabel }}</el-tag>
            </div>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>
                系统配置
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <div v-else class="user-trigger guest" @click="router.push('/login')">
          <el-avatar :size="36" class="user-avatar guest-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="user-email">未登录 · 点击登录</span>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <h1>{{ (route.meta.title as string) || '枫桥智诉' }}</h1>
      </header>
      <section class="content">
        <router-view />
      </section>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 240px;
  background: var(--brand-sidebar);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100vh;
  overflow-y: auto;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 8px 10px 24px;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  display: grid;
  place-items: center;
  font-size: 20px;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.brand-sub {
  font-size: 12px;
  color: #94a3b8;
}

.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 10px;
  color: #cbd5e1;
  text-decoration: none;
  transition: all 0.15s;
}

.nav-item:hover {
  background: rgb(255 255 255 / 6%);
  color: #fff;
}

.nav-item.active {
  background: rgb(249 115 22 / 18%);
  color: #fb923c;
  font-weight: 600;
}

.sidebar-footer {
  border-top: 1px solid #334155;
  padding-top: 14px;
}

.sidebar-footer :deep(.el-dropdown) {
  display: block;
  width: 100%;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.user-trigger:hover {
  background: rgb(255 255 255 / 6%);
}

.user-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-weight: 600;
}

.guest-avatar {
  background: #475569;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.user-email {
  font-size: 13px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  background: linear-gradient(180deg, #ffffff 0%, #fafaf9 100%);
  border-bottom: 1px solid rgb(15 23 42 / 5%);
  box-shadow: 0 1px 3px rgb(15 23 42 / 3%);
  padding: 18px 28px;
}

.topbar h1 {
  position: relative;
  margin: 0;
  padding-left: 14px;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.topbar h1::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 18px;
  background: linear-gradient(180deg, #f97316, #ea580c);
  border-radius: 2px;
}

.content {
  flex: 1;
  padding: 24px 28px;
}

:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
