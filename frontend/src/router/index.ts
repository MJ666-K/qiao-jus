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
          path: 'datasets',
          name: 'datasets',
          component: () => import('@/views/DatasetsView.vue'),
          meta: { title: '知识库' },
        },
        {
          path: 'documents',
          name: 'documents',
          component: () => import('@/views/DocumentsView.vue'),
          meta: { title: '文档管理' },
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
          meta: { title: '检索' },
        },
        {
          path: 'graph',
          name: 'graph',
          component: () => import('@/views/GraphView.vue'),
          meta: { title: '知识图谱' },
        },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '智能问答' },
        },
        {
          path: 'chat/:conversationId?',
          name: 'chat-with-conversation',
          component: () => import('@/views/ChatView.vue'),
          meta: { title: '智能问答' },
        },
        {
          path: 'reports',
          name: 'reports-list',
          component: () => import('@/views/ReportsListView.vue'),
          meta: { title: '分析报告' },
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
