<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  Collection,
  DataAnalysis,
  Document,
  Grid,
  Search,
  Setting,
  Share,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { path: '/dashboard', label: '概览', icon: DataAnalysis },
  { path: '/datasets', label: '知识库', icon: Collection },
  { path: '/documents', label: '文档', icon: Document },
  { path: '/search', label: '检索', icon: Search },
  { path: '/graph', label: '图谱', icon: Share },
  { path: '/chat', label: '问答', icon: ChatDotRound },
]

const activePath = computed(() => route.path)

const avatarText = computed(() => {
  const email = auth.user?.email
  if (!email) return '?'
  return email.charAt(0).toUpperCase()
})

function goSettings() {
  router.push('/settings')
}

function handleUserCommand(cmd: string) {
  if (cmd === 'settings') goSettings()
  else if (cmd === 'logout') logout()
}

function logout() {
  auth.logout()
  router.push('/login')
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
        <div class="brand-icon">
          <el-icon><Grid /></el-icon>
        </div>
        <div>
          <div class="brand-title">枫桥智诉</div>
          <div class="brand-sub">知识库 · 图谱底座</div>
        </div>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: activePath.startsWith(item.path) }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <el-dropdown v-if="auth.user" trigger="click" placement="top-start" @command="handleUserCommand">
          <div class="user-trigger">
            <el-avatar :size="36" class="user-avatar">{{ avatarText }}</el-avatar>
            <span class="user-email">{{ auth.user.email }}</span>
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
  background: linear-gradient(135deg, #2563eb, #7c3aed);
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
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #cbd5e1;
  text-decoration: none;
  transition: background 0.15s;
}

.nav-item:hover,
.nav-item.active {
  background: rgb(37 99 235 / 25%);
  color: #fff;
}

.sidebar-footer {
  border-top: 1px solid #334155;
  padding-top: 14px;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.user-trigger:hover {
  background: rgb(255 255 255 / 6%);
}

.user-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #fff;
  font-weight: 600;
}

.guest-avatar {
  background: #475569;
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
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  padding: 16px 28px;
}

.topbar h1 {
  margin: 0;
  font-size: 18px;
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
