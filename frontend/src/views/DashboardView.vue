<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchStats } from '@/api/stats'
import { listDocuments } from '@/api/documents'
import { listReports } from '@/api/reports'
import type { DocumentItem, Report, Stats } from '@/types'

const router = useRouter()
const loading = ref(true)
const stats = ref<Stats | null>(null)
const myDocuments = ref<DocumentItem[]>([])
const myReports = ref<Report[]>([])

const userStats = computed(() => ({
  docs: myDocuments.value.length,
  pendingDocs: myDocuments.value.filter((d) => d.status !== 'done' && d.status !== 'failed').length,
  reports: myReports.value.length,
  doneReports: myReports.value.filter((r) => r.status === 'done').length,
}))

const userCards = computed(() => [
  { key: 'docs', label: '我的文档', value: userStats.value.docs, color: '#2563eb', action: () => router.push('/documents') },
  { key: 'pendingDocs', label: '处理中', value: userStats.value.pendingDocs, color: '#d97706', action: () => router.push('/documents') },
  { key: 'reports', label: '我的报告', value: userStats.value.reports, color: '#7c3aed', action: () => router.push('/reports') },
  { key: 'doneReports', label: '报告完成', value: userStats.value.doneReports, color: '#059669', action: () => router.push('/reports') },
])

const platformCards = [
  { key: 'datasets', label: '平台知识库', color: '#0ea5e9' },
  { key: 'documents', label: '平台文档', color: '#4f46e5' },
  { key: 'documents_done', label: '已处理', color: '#059669' },
  { key: 'chunks', label: '文本块', color: '#db2777' },
] as const

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
  { key: 'm1', label: '纠纷研判', desc: '上传纠纷材料，AI 生成案由/证据/调解建议', route: '/reports/new', color: '#2563eb' },
  { key: 'm2', label: '合同审查', desc: '上传合同，AI 识别风险条款并给修改建议', route: '/reports/new', color: '#7c3aed' },
  { key: 'm3', label: '用工排查', desc: '粘贴用工描述，规则引擎 + 法规库自动核查', route: '/reports/new', color: '#059669' },
  { key: 'm4', label: '文书生成', desc: '输入案由与事实，生成起诉状草稿', route: '/reports/new', color: '#d97706' },
  { key: 'm5', label: '证据指引', desc: '选择案由，输出证据清单 + 举证流程', route: '/reports/new', color: '#db2777' },
]

onMounted(async () => {
  try {
    const [s, docs, reps] = await Promise.all([
      fetchStats(),
      listDocuments({}).catch(() => []),
      listReports().catch(() => []),
    ])
    stats.value = s
    myDocuments.value = docs.filter((d: DocumentItem) =>
      ['contract', 'dispute', 'report'].includes(String(d.metadata?.doc_type || ''))
    )
    myReports.value = reps
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading">
    <p class="page-desc">个人工作台 · 一站式查看我的文档、报告与快速入口</p>

    <div class="stat-grid">
      <div
        v-for="card in userCards"
        :key="card.key"
        class="stat-card card-panel clickable"
        @click="card.action()"
      >
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
      </div>
    </div>

    <div class="section">
      <h3 class="section-title">五大业务模块</h3>
      <div class="module-grid">
        <div
          v-for="m in moduleCards"
          :key="m.key"
          class="module-card"
          :style="{ borderLeftColor: m.color }"
          @click="router.push(m.route)"
        >
          <div class="module-label" :style="{ color: m.color }">{{ m.label }}</div>
          <div class="module-desc">{{ m.desc }}</div>
        </div>
      </div>
    </div>

    <div class="two-col">
      <div class="card-panel">
        <div class="section-header">
          <h3 class="section-title">最近报告</h3>
          <el-button link type="primary" @click="router.push('/reports')">查看全部</el-button>
        </div>
        <el-empty v-if="!recentReports.length" :image-size="60" description="暂无报告">
          <el-button type="primary" size="small" @click="router.push('/reports/new')">立即生成</el-button>
        </el-empty>
        <div v-else>
          <div
            v-for="r in recentReports"
            :key="r.id"
            class="list-row"
            @click="router.push({ name: 'report-view', params: { id: r.id } })"
          >
            <span class="list-title">{{ reportTypeLabel[r.type] || r.type }}</span>
            <span class="list-summary">{{ (r.summary || '生成中...').slice(0, 40) }}</span>
            <el-tag
              :type="r.status === 'done' ? 'success' : r.status === 'failed' ? 'danger' : 'warning'"
              size="small"
            >
              {{ r.status === 'done' ? '完成' : r.status === 'failed' ? '失败' : '生成中' }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="card-panel">
        <div class="section-header">
          <h3 class="section-title">最近文档</h3>
          <el-button link type="primary" @click="router.push('/documents')">查看全部</el-button>
        </div>
        <el-empty v-if="!recentDocs.length" :image-size="60" description="暂无文档">
          <el-button type="primary" size="small" @click="router.push('/documents')">去上传</el-button>
        </el-empty>
        <div v-else>
          <div
            v-for="d in recentDocs"
            :key="d.id"
            class="list-row"
          >
            <span class="list-title">{{ d.title }}</span>
            <el-tag
              :type="d.status === 'done' ? 'success' : d.status === 'failed' ? 'danger' : 'info'"
              size="small"
            >
              {{ d.status === 'done' ? '已处理' : d.status === 'failed' ? '失败' : d.status }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header">
        <h3 class="section-title">平台知识库（管理员视角）</h3>
      </div>
      <div class="stat-grid">
        <div v-for="card in platformCards" :key="card.key" class="stat-card card-panel small">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color, fontSize: '22px' }">
            {{ stats?.[card.key] ?? '-' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.stat-card {
  padding: 16px;
  cursor: default;
}

.stat-card.clickable {
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.stat-card.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgb(0 0 0 / 10%);
}

.stat-card.small {
  padding: 12px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}

.section {
  margin-top: 24px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.module-card {
  border: 1px solid #e2e8f0;
  border-left: 4px solid #2563eb;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.15s;
}

.module-card:hover {
  background: #f8fafc;
  transform: translateY(-1px);
}

.module-label {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
}

.module-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 24px;
}

@media (max-width: 900px) {
  .two-col {
    grid-template-columns: 1fr;
  }
}

.list-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 4px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background 0.1s;
}

.list-row:hover {
  background: #f8fafc;
}

.list-row:last-child {
  border-bottom: none;
}

.list-title {
  font-size: 13px;
  font-weight: 600;
  min-width: 90px;
  color: #1e293b;
}

.list-summary {
  flex: 1;
  font-size: 13px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
