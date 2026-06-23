<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useReportsStore } from '@/stores/reports'

const router = useRouter()
const store = useReportsStore()

const reportTypeLabel: Record<string, string> = {
  contract_review: '合同审查',
  dispute_analysis: '纠纷研判',
  labor_risk: '用工风险',
  litigation_draft: '诉讼文书',
  evidence_checklist: '证据指引',
}

const statusTagType: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  done: 'success',
  pending: 'info',
  generating: 'warning',
  failed: 'danger',
}

const statusLabel: Record<string, string> = {
  done: '完成',
  pending: '排队中',
  generating: '生成中',
  failed: '失败',
}

function viewReport(id: string) {
  router.push({ name: 'report-view', params: { id } })
}

function newReport() {
  router.push({ name: 'report-new' })
}

onMounted(() => {
  store.loadList()
})
</script>

<template>
  <div>
    <div class="header-row">
      <p class="page-desc">
        分析报告列表。点击「生成报告」选择业务模块（合同审查/纠纷研判/用工风险/文书生成/证据指引），完成后可基于报告发起智能问答。
      </p>
      <el-button type="primary" @click="newReport">生成报告</el-button>
    </div>

    <div v-loading="store.loading" class="card-panel">
      <el-empty v-if="!store.reports.length && !store.loading" description="暂无报告">
        <el-button type="primary" @click="newReport">立即生成</el-button>
      </el-empty>

      <el-table v-else :data="store.reports" stripe>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            {{ reportTypeLabel[row.type] || row.type }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType[row.status]" size="small">
              {{ statusLabel[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="320">
          <template #default="{ row }">
            <span class="summary">{{ row.summary || (row.status === 'done' ? '（无摘要）' : '生成中...') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">
            <span v-if="row.status === 'done'">{{ row.confidence }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="风险项" width="80">
          <template #default="{ row }">
            <span v-if="row.status === 'done'">{{ row.risk_items.length }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="生成时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewReport(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.summary {
  color: #475569;
  font-size: 13px;
}

.muted {
  color: #cbd5e1;
}
</style>
