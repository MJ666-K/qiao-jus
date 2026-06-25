import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '概览' },
        },
        {
          path: 'documents',
          name: 'documents',
          component: () => import('@/views/DocumentsView.vue'),
          meta: { title: '我的文档' },
        },
        {
          path: 'documents/:id/chunks',
          name: 'chunk-editor',
          component: () => import('@/views/ChunkEditorView.vue'),
          meta: { title: '文本块管理' },
        },
        {
          path: 'search',
          name: 'search',
          component: () => import('@/views/SearchView.vue'),
          meta: { title: '检索测试' },
        },
        {
          path: 'graph',
          name: 'graph',
          component: () => import('@/views/GraphView.vue'),
          meta: { title: '知识图谱', fluid: true },
        },
        {
          path: 'assistants',
          name: 'assistants',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '我的助手', fillHeight: true, fluid: true },
        },
        {
          path: 'assistants/:assistantId',
          name: 'assistant-home',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '我的助手', fillHeight: true, fluid: true },
        },
        {
          path: 'assistants/:assistantId/c/:conversationId',
          name: 'assistant-chat',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '我的助手', fillHeight: true, fluid: true },
        },
        {
          path: 'chat',
          redirect: '/assistants',
        },
        {
          path: 'chat/:conversationId',
          name: 'chat-legacy',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '我的助手', fillHeight: true, fluid: true },
        },
        {
          path: 'reports',
          name: 'reports-list',
          component: () => import('@/views/ReportsListView.vue'),
          meta: { title: '我的报告' },
        },
        {
          path: 'reports/new',
          name: 'report-new',
          component: () => import('@/views/NewReportView.vue'),
          meta: { title: '生成报告' },
        },
        {
          path: 'reports/:id',
          name: 'report-view',
          component: () => import('@/views/ReportView.vue'),
          meta: { title: '报告详情' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: '系统配置' },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  const auth = useAuthStore()
  if (!auth.ready) {
    await auth.restore()
  }

  if (!getToken() || !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
