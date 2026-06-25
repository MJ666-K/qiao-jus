<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChatDotRound,
  Document,
  DocumentCopy,
  Files,
  FolderOpened,
  Right,
  Tools,
} from '@element-plus/icons-vue'
import { listAllDocuments } from '@/api/documents'
import { listReports } from '@/api/reports'
import { useAuthStore } from '@/stores/auth'
import type { DocumentItem, Report } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const myDocuments = ref<DocumentItem[]>([])
const myReports = ref<Report[]>([])

const displayName = computed(
  () => auth.user?.display_name || auth.user?.email?.split('@')[0] || '用户',
)

const userStats = computed(() => ({
  docs: myDocuments.value.length,
  pendingDocs: myDocuments.value.filter((d) => d.status !== 'done' && d.status !== 'failed').length,
  reports: myReports.value.length,
  doneReports: myReports.value.filter((r) => r.status === 'done').length,
}))

const userCards = computed(() => [
  { key: 'docs', label: '我的文档', value: userStats.value.docs, icon: Files, route: '/documents' },
  { key: 'pending', label: '处理中', value: userStats.value.pendingDocs, icon: FolderOpened, route: '/documents' },
  { key: 'reports', label: '我的报告', value: userStats.value.reports, icon: DocumentCopy, route: '/reports' },
  { key: 'done', label: '已完成', value: userStats.value.doneReports, icon: Document, route: '/reports' },
])

const recentReports = computed(() => myReports.value.slice(0, 5))
const recentDocs = computed(() => myDocuments.value.slice(0, 5))

const reportTypeLabel: Record<string, string> = {
  contract_review: '合同审查',
  dispute_analysis: '纠纷研判',
  labor_risk: '用工风险',
  litigation_draft: '诉讼文书',
  evidence_checklist: '证据指引',
}

const moduleCards = [
  { key: 'm1', label: '纠纷研判', desc: '案由 · 证据 · 调解建议', route: '/reports/new', tone: '#f97316' },
  { key: 'm2', label: '合同审查', desc: '风险条款识别与修改', route: '/reports/new', tone: '#ea580c' },
  { key: 'm3', label: '用工排查', desc: '法规规则自动核查', route: '/reports/new', tone: '#d97706' },
  { key: 'm4', label: '文书生成', desc: '起诉状等文书草稿', route: '/reports/new', tone: '#fb923c' },
  { key: 'm5', label: '证据指引', desc: '证据清单与举证流程', route: '/reports/new', tone: '#c2410c' },
]

function reportStatusTag(status: string) {
  if (status === 'done') return { type: 'success' as const, text: '完成' }
  if (status === 'failed') return { type: 'danger' as const, text: '失败' }
  return { type: 'warning' as const, text: '生成中' }
}

function docStatusTag(status: string) {
  if (status === 'done') return { type: 'success' as const, text: '已处理' }
  if (status === 'failed') return { type: 'danger' as const, text: '失败' }
  return { type: 'info' as const, text: status }
}

onMounted(async () => {
  try {
    const [docs, reps] = await Promise.all([
      listAllDocuments({ status_filter: 'done', uploaded_only: true }).catch(() => []),
      listReports().catch(() => []),
    ])
    myDocuments.value = docs.filter((d: DocumentItem) =>
      ['contract', 'dispute', 'report'].includes(String(d.metadata?.doc_type || '')),
    )
    myReports.value = reps
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="dashboard">
    <!-- 欢迎区 -->
    <section class="hero card-panel">
      <div class="hero-decor" aria-hidden="true" />
      <div class="hero-text">
        <p class="hero-greet">你好，{{ displayName }}</p>
        <h2 class="hero-title">法律智能辅助<span class="emph">工作台</span></h2>
        <p class="hero-sub">上传材料、生成报告、我的助手，一站完成</p>
      </div>
      <div class="hero-actions">
        <el-button type="primary" size="large" :icon="Tools" @click="router.push('/reports/new')">
          生成报告
        </el-button>
        <el-button size="large" :icon="ChatDotRound" @click="router.push('/assistants')">
          我的助手
        </el-button>
      </div>
    </section>

    <!-- 个人数据 -->
    <section class="stat-row">
      <div
        v-for="card in userCards"
        :key="card.key"
        class="stat-card"
        @click="router.push(card.route)"
      >
        <div class="stat-icon">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
        <el-icon class="stat-arrow"><Right /></el-icon>
      </div>
    </section>

    <!-- 业务模块 -->
    <section class="block module-block">
      <div class="section-head">
        <h3>业务模块</h3>
        <span class="hint">选择场景快速开始</span>
      </div>
      <div class="module-grid">
        <div
          v-for="m in moduleCards"
          :key="m.key"
          class="module-card"
          @click="router.push(m.route)"
        >
          <div class="module-dot" :style="{ background: m.tone }" />
          <div class="module-name">{{ m.label }}</div>
          <div class="module-desc">{{ m.desc }}</div>
        </div>
      </div>
    </section>

    <!-- 最近动态 -->
    <section class="activity-grid">
      <div class="activity-card card-panel">
        <div class="section-head">
          <h3>最近报告</h3>
          <el-button link type="primary" @click="router.push('/reports')">全部</el-button>
        </div>
        <el-empty v-if="!recentReports.length" :image-size="56" description="暂无报告">
          <el-button type="primary" size="small" @click="router.push('/reports/new')">去生成</el-button>
        </el-empty>
        <ul v-else class="activity-list">
          <li
            v-for="r in recentReports"
            :key="r.id"
            class="activity-item"
            @click="router.push({ name: 'report-view', params: { id: r.id } })"
          >
            <div class="item-main">
              <span class="item-title">{{ reportTypeLabel[r.type] || r.type }}</span>
              <span class="item-desc">{{ r.summary || '生成中…' }}</span>
            </div>
            <el-tag v-bind="reportStatusTag(r.status)" size="small" round>
              {{ reportStatusTag(r.status).text }}
            </el-tag>
          </li>
        </ul>
      </div>

      <div class="activity-card card-panel">
        <div class="section-head">
          <h3>最近文档</h3>
          <el-button link type="primary" @click="router.push('/documents')">全部</el-button>
        </div>
        <el-empty v-if="!recentDocs.length" :image-size="56" description="暂无文档">
          <el-button type="primary" size="small" @click="router.push('/documents')">去上传</el-button>
        </el-empty>
        <ul v-else class="activity-list">
          <li
            v-for="d in recentDocs"
            :key="d.id"
            class="activity-item"
            @click="router.push('/documents')"
          >
            <div class="item-main">
              <span class="item-title">{{ d.title }}</span>
              <span class="item-desc">{{ new Date(d.created_at).toLocaleString('zh-CN') }}</span>
            </div>
            <el-tag v-bind="docStatusTag(d.status)" size="small" round>
              {{ docStatusTag(d.status).text }}
            </el-tag>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--gap-section);
  min-width: 0;
  max-width: 100%;
}

/* Hero */
.hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px;
  background: rgb(255 255 255 / 90%);
  border: 1px solid var(--border-default);
}

.hero-decor {
  position: absolute;
  top: -40%;
  right: -5%;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--glow-amber), transparent 70%);
  filter: blur(8px);
  pointer-events: none;
}

.hero-greet {
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--brand-primary-dark);
  font-weight: 500;
}

.hero-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.hero-title .emph {
  color: var(--brand-primary);
  font-style: italic;
}

.hero-sub {
  margin: 0;
  font-size: 14px;
  color: var(--text-body);
}

.hero-text {
  position: relative;
  z-index: 1;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

/* Stats */
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--brand-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgb(249 115 22 / 10%);
  border-color: var(--brand-primary-light);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--brand-primary-soft), #ffedd5);
  color: var(--brand-primary-dark);
  display: grid;
  place-items: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.stat-arrow {
  color: #d6d3d1;
  font-size: 14px;
  flex-shrink: 0;
}

.stat-card:hover .stat-arrow {
  color: var(--brand-primary);
}

/* Modules */
.module-block {
  background: linear-gradient(180deg, #fffbf5 0%, #fff7ed 100%);
  border: 1px solid rgb(249 115 22 / 12%);
  border-radius: var(--radius-md);
  padding: 18px 20px 20px;
}

.module-card {
  background: rgb(255 255 255 / 85%);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 18px 16px;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: var(--shadow-sm);
}

.module-card:hover {
  border-color: #fdba74;
  background: var(--brand-primary-soft);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgb(249 115 22 / 8%);
}

.module-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-bottom: 12px;
}

.module-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.module-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}

/* Activity */
.activity-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
}

.activity-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-height: min(360px, calc(100vh - 220px));
  overflow: hidden;
  background: linear-gradient(180deg, #fffbf5 0%, #fafaf9 100%);
  border-color: rgb(249 115 22 / 10%);
}

.activity-list {
  list-style: none;
  margin: 8px 0 0;
  padding: 4px 6px;
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  background: rgb(255 255 255 / 55%);
  border-radius: var(--radius-sm);
}

.activity-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
  border-bottom: 1px solid rgb(28 25 23 / 5%);
  min-width: 0;
}

.activity-item :deep(.el-tag) {
  flex-shrink: 0;
}

.activity-item:last-child {
  border-bottom: none;
}

.activity-item:hover {
  background: var(--brand-primary-soft);
}

.item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-desc {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .module-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .stat-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .activity-grid {
    grid-template-columns: 1fr;
  }

  .module-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .stat-row {
    grid-template-columns: 1fr;
  }

  .module-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    width: 100%;
    flex-direction: column;
  }

  .hero-actions .el-button {
    width: 100%;
    margin: 0;
  }
}
</style>
