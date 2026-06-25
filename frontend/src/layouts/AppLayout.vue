<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Avatar,
  DataAnalysis,
  DocumentCopy,
  Expand,
  Files,
  Fold,
  Grid,
  Search,
  Setting,
  Share,
  SwitchButton,
  Tools,
  User,
} from "@element-plus/icons-vue";
import { useAuthStore } from "@/stores/auth";

interface NavItem {
  path: string;
  label: string;
  icon: typeof Grid;
  exact?: boolean;
  adminOnly?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const allNavItems: NavItem[] = [
  { path: "/dashboard", label: "概览", icon: DataAnalysis },
  { path: "/documents", label: "我的文档", icon: Files },
  { path: "/reports/new", label: "生成报告", icon: Tools, exact: true },
  { path: "/reports", label: "我的报告", icon: DocumentCopy },
  { path: "/assistants", label: "我的助手", icon: Avatar },
  { path: "/search", label: "检索测试", icon: Search, adminOnly: true },
  { path: "/graph", label: "知识图谱", icon: Share, adminOnly: true },
  { path: "/settings", label: "系统配置", icon: Setting },
];

const navGroups = computed<NavGroup[]>(() => {
  const isAdmin = auth.user?.role === "admin";
  const work: NavItem[] = [];
  const platform: NavItem[] = [];
  for (const item of allNavItems) {
    if (item.adminOnly && !isAdmin) continue;
    if (item.adminOnly) platform.push(item);
    else work.push(item);
  }
  const groups: NavGroup[] = [{ label: "工作台", items: work }];
  if (platform.length) groups.push({ label: "平台管理", items: platform });
  return groups;
});

const isAdmin = computed(() => auth.user?.role === "admin");
const roleLabel = computed(() => (isAdmin.value ? "管理员" : "普通用户"));

const isFluid = computed(() =>
  Boolean(route.meta.fluid || route.meta.fillHeight),
);

const SIDEBAR_COLLAPSED_KEY = "app_sidebar_collapsed";
const sidebarCollapsed = ref(
  localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1",
);

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  localStorage.setItem(
    SIDEBAR_COLLAPSED_KEY,
    sidebarCollapsed.value ? "1" : "0",
  );
}

function isActive(item: NavItem): boolean {
  if (item.exact) return route.path === item.path;
  if (item.path === "/reports") {
    return (
      route.path.startsWith("/reports") &&
      !route.path.startsWith("/reports/new")
    );
  }
  return (
    route.path.startsWith(item.path) && route.path.length >= item.path.length
  );
}

const avatarText = computed(() => {
  const name = auth.user?.display_name || auth.user?.email;
  if (!name) return "?";
  return name.charAt(0).toUpperCase();
});

const displayName = computed(
  () => auth.user?.display_name || auth.user?.email?.split("@")[0] || "—",
);

function logout() {
  auth.logout();
  router.push("/login");
}

onMounted(async () => {
  if (!auth.user && localStorage.getItem("ks_token")) {
    await auth.ensureUser();
  }
});
</script>

<template>
  <div class="layout">
    <div class="ambient" aria-hidden="true">
      <div class="ambient-glow ambient-glow-a" />
      <div class="ambient-glow ambient-glow-b" />
      <div class="ambient-glow ambient-glow-c" />
    </div>

    <aside class="sidebar" :class="{ 'sidebar--collapsed': sidebarCollapsed }">
      <div class="brand">
        <div class="brand-icon">枫</div>
        <div v-show="!sidebarCollapsed" class="brand-text">
          <div class="brand-title">枫桥智诉</div>
          <div class="brand-sub">法律智能辅助</div>
        </div>
        <button
          type="button"
          class="sidebar-toggle"
          :title="sidebarCollapsed ? '展开导航' : '收起导航'"
          @click="toggleSidebar"
        >
          <el-icon
            ><component :is="sidebarCollapsed ? Expand : Fold"
          /></el-icon>
        </button>
      </div>

      <nav class="nav">
        <div v-for="group in navGroups" :key="group.label" class="nav-group">
          <div v-show="!sidebarCollapsed" class="nav-group-label">
            {{ group.label }}
          </div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item) }"
            :title="sidebarCollapsed ? item.label : undefined"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span v-show="!sidebarCollapsed">{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div
          v-if="auth.user"
          class="user-bar"
          :class="{ 'user-bar--compact': sidebarCollapsed }"
        >
          <div class="user-profile">
            <el-avatar :size="36" class="user-avatar">{{
              avatarText
            }}</el-avatar>
            <div v-show="!sidebarCollapsed" class="user-info">
              <span class="user-name">{{ displayName }}</span>
              <span class="user-role">{{ roleLabel }}</span>
            </div>
          </div>
          <button
            type="button"
            class="logout-btn"
            title="退出登录"
            @click="logout"
          >
            <el-icon><SwitchButton /></el-icon>
          </button>
        </div>

        <div v-else class="user-trigger guest" @click="router.push('/login')">
          <el-avatar :size="36" class="user-avatar guest-avatar">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span v-show="!sidebarCollapsed" class="user-name">点击登录</span>
        </div>
      </div>
    </aside>

    <main class="main">
      <header v-if="!route.meta.fillHeight" class="topbar">
        <div class="topbar-inner">
          <h1 class="page-heading">
            {{ (route.meta.title as string) || "枫桥智诉" }}
          </h1>
          <p class="page-sub">AI 法律智能辅助平台</p>
        </div>
      </header>

      <section
        class="content"
        :class="{ 'content--fill': route.meta.fillHeight }"
      >
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
  position: relative;
  display: flex;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: var(--brand-bg);
}

/* 登录页同款氛围光晕 */
.ambient {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.ambient-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
}

.ambient-glow-a {
  width: 480px;
  height: 480px;
  top: -8%;
  left: 18%;
  background: radial-gradient(circle, var(--glow-mint), transparent 68%);
  animation: float-a 12s ease-in-out infinite;
}

.ambient-glow-b {
  width: 420px;
  height: 420px;
  top: 35%;
  right: 8%;
  background: radial-gradient(circle, var(--glow-rose), transparent 68%);
  animation: float-b 14s ease-in-out infinite;
}

.ambient-glow-c {
  width: 360px;
  height: 360px;
  bottom: 5%;
  left: 42%;
  background: radial-gradient(circle, var(--glow-amber), transparent 68%);
  animation: float-c 10s ease-in-out infinite;
}

@keyframes float-a {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(24px, 18px);
  }
}

@keyframes float-b {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(-20px, 24px);
  }
}

@keyframes float-c {
  0%,
  100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(16px, -16px);
  }
}

/* 浅色侧边栏 — 对齐登录右侧白底 */
.sidebar {
  position: relative;
  z-index: 2;
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: rgb(255 255 255 / 92%);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: var(--text-primary);
  display: flex;
  flex-direction: column;
  padding: 16px 14px;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: 1px solid var(--brand-sidebar-border);
  box-shadow: 2px 0 16px rgb(28 25 23 / 3%);
  transition:
    width 0.22s ease,
    padding 0.22s ease;
}

.sidebar--collapsed {
  width: var(--sidebar-collapsed-width);
  padding: 16px 10px;
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 4px 6px 18px;
  position: relative;
}

.sidebar--collapsed .brand {
  flex-direction: column;
  gap: 8px;
  padding: 4px 2px 14px;
}

.sidebar-toggle {
  margin-left: auto;
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--text-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.15s;
}

.sidebar--collapsed .sidebar-toggle {
  margin-left: 0;
}

.sidebar-toggle:hover {
  border-color: var(--brand-primary-light);
  color: var(--brand-primary);
  background: var(--brand-primary-soft);
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  display: grid;
  place-items: center;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 4px 12px rgb(249 115 22 / 30%);
  flex-shrink: 0;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--text-primary);
}

.brand-sub {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  padding: 0 2px;
}

.nav-group-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  padding: 0 10px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid transparent;
  transition: all 0.15s;
  margin-bottom: 4px;
}

.sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 10px 8px;
}

.nav-icon {
  font-size: 17px;
  color: var(--text-muted);
  transition: color 0.15s;
}

.nav-item:hover {
  background: var(--brand-sidebar-hover);
  color: var(--text-primary);
  border-color: var(--border-subtle);
}

.nav-item:hover .nav-icon {
  color: var(--brand-primary);
}

.nav-item.active {
  background: var(--brand-sidebar-active);
  color: var(--brand-primary-dark);
  font-weight: 600;
  border-color: var(--brand-primary-light);
  box-shadow: 0 0 0 1px rgb(249 115 22 / 8%);
}

.nav-item.active .nav-icon {
  color: var(--brand-primary);
}

.sidebar-footer {
  border-top: 1px solid var(--border-subtle);
  padding-top: 12px;
  margin-top: 8px;
}

.user-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
}

.user-bar--compact {
  flex-direction: column;
  padding: 6px 4px;
  gap: 6px;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.user-bar--compact .user-profile {
  justify-content: center;
}

.logout-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--text-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.15s;
}

.logout-btn:hover {
  color: #ef4444;
  border-color: #fecaca;
  background: #fef2f2;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.user-trigger.guest:hover {
  background: var(--brand-sidebar-hover);
  border-color: var(--border-subtle);
}

.user-avatar {
  flex-shrink: 0;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}

.guest-avatar {
  background: #e5e7eb;
  color: #6b7280;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 11px;
  color: var(--text-muted);
}

/* 主内容区 */
.main {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.topbar {
  height: var(--topbar-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 0 var(--page-padding-x);
  background: rgb(255 255 255 / 88%);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border-default);
}

.topbar-inner {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.page-heading {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.page-sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.page-sub::before {
  content: "·";
  margin-right: 12px;
  color: var(--border-strong);
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
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

@media (max-width: 768px) {
  .sidebar {
    width: var(--sidebar-collapsed-width);
    padding: 12px 8px;
  }

  .brand-text,
  .nav-group-label,
  .nav-item span,
  .user-info,
  .user-name,
  .page-sub {
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
