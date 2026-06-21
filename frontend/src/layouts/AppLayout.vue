<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound,
  Collection,
  DataAnalysis,
  Document,
  Grid,
  Search,
  Share,
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

const tenantLabel = computed(() => {
  const id = auth.user?.tenant_id
  return id ? id.slice(0, 8) : '-'
})

function logout() {
  auth.logout()
  router.push('/login')
}
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
        <div class="user-email">{{ auth.user?.email ?? '未登录' }}</div>
        <div class="tenant-id">租户 {{ tenantLabel }}</div>
        <el-button link type="danger" @click="logout">退出登录</el-button>
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
  font-size: 12px;
}

.user-email {
  color: #e2e8f0;
  margin-bottom: 4px;
}

.tenant-id {
  color: #64748b;
  margin-bottom: 8px;
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
</style>
