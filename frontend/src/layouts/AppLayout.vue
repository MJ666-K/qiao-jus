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

interface NavGroup {
  label: string
  items: NavItem[]
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

const navGroups = computed<NavGroup[]>(() => {
  const isAdmin = auth.user?.role === 'admin'
  const work: NavItem[] = []
  const platform: NavItem[] = []
  for (const item of allNavItems) {
    if (item.adminOnly && !isAdmin) continue
    if (item.adminOnly) platform.push(item)
    else work.push(item)
  }
  const groups: NavGroup[] = [{ label: '工作台', items: work }]
  if (platform.length) groups.push({ label: '平台管理', items: platform })
  return groups
})

const isAdmin = computed(() => auth.user?.role === 'admin')
const roleLabel = computed(() => (isAdmin.value ? '管理员' : '普通用户'))

const isFluid = computed(() => Boolean(route.meta.fluid || route.meta.fillHeight))

function isActive(item: NavItem): boolean {
  if (item.exact) return route.path === item.path
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

function handleUserCommand(cmd: string) {
  if (cmd === 'settings') router.push('/settings')
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
        <div class="brand-text">
          <div class="brand-title">枫桥智诉</div>
          <div class="brand-sub">法律智能辅助</div>
        </div>
      </div>

      <nav class="nav">
        <div v-for="group in navGroups" :key="group.label" class="nav-group">
          <div class="nav-group-label">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item) }"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <el-dropdown v-if="auth.user" trigger="click" placement="top-start" @command="handleUserCommand">
          <div class="user-trigger">
            <el-avatar :size="34" class="user-avatar">{{ avatarText }}</el-avatar>
            <div class="user-info">
              <span class="user-name">{{ displayName }}</span>
              <span class="user-role">{{ roleLabel }}</span>
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
          <el-avatar :size="34" class="user-avatar guest-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="user-name">点击登录</span>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <h1 class="page-heading">{{ (route.meta.title as string) || '枫桥智诉' }}</h1>
      </header>

      <section class="content" :class="{ 'content--fill': route.meta.fillHeight }">
        <div
          class="page-shell"
          :class="{
            'page-shell--fluid': isFluid,
            'page-shell--fill': route.meta.fillHeight,
          }"
        >
          <router-view />
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  background: var(--brand-bg);
}

/* Sidebar */
.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--brand-sidebar);
  color: var(--text-inverse);
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  border-right: 1px solid rgb(0 0 0 / 20%);
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 6px 8px 20px;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  display: grid;
  place-items: center;
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 4px 12px rgb(249 115 22 / 35%);
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.brand-sub {
  font-size: 11px;
  color: #78716c;
  margin-top: 1px;
}

.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding: 0 2px;
}

.nav-group-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #57534e;
  padding: 0 10px 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  color: #a8a29e;
  text-decoration: none;
  font-size: 13px;
  transition: background 0.15s, color 0.15s;
  margin-bottom: 2px;
}

.nav-icon {
  font-size: 16px;
  opacity: 0.85;
}

.nav-item:hover {
  background: var(--brand-sidebar-hover);
  color: #e7e5e4;
}

.nav-item.active {
  background: var(--brand-sidebar-active);
  color: #fdba74;
  font-weight: 600;
}

.nav-item.active .nav-icon {
  opacity: 1;
  color: #f97316;
}

.sidebar-footer {
  border-top: 1px solid rgb(255 255 255 / 8%);
  padding-top: 12px;
  margin-top: 8px;
}

.sidebar-footer :deep(.el-dropdown) {
  display: block;
  width: 100%;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.user-trigger:hover {
  background: var(--brand-sidebar-hover);
}

.user-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.guest-avatar {
  background: #44403c;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  color: #e7e5e4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 11px;
  color: #78716c;
}

/* Main */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: var(--topbar-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0 var(--page-padding-x);
  background: var(--brand-surface);
  border-bottom: 1px solid var(--border-subtle);
}

.page-heading {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
}

.content {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: var(--page-padding-y) var(--page-padding-x);
}

.content--fill {
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.content--fill .page-shell--fill {
  flex: 1;
  min-height: 0;
}

:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .sidebar {
    width: 64px;
    padding: 12px 8px;
  }

  .brand-text,
  .nav-group-label,
  .nav-item span,
  .user-info,
  .user-name {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 10px;
  }

  .brand {
    justify-content: center;
    padding-bottom: 12px;
  }
}
</style>
