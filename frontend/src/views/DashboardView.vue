<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchStats } from '@/api/stats'
import type { Stats } from '@/types'

const loading = ref(true)
const stats = ref<Stats | null>(null)

const cards = [
  { key: 'datasets', label: '知识库', color: '#2563eb' },
  { key: 'documents', label: '文档总数', color: '#4f46e5' },
  { key: 'documents_done', label: '已处理', color: '#059669' },
  { key: 'chunks', label: '文本块', color: '#7c3aed' },
  { key: 'qdrant_points', label: '向量点', color: '#db2777' },
] as const

onMounted(async () => {
  try {
    stats.value = await fetchStats()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading">
    <p class="page-desc">平台知识库运行状态与入库流水线概览</p>

    <div class="stat-grid">
      <div v-for="card in cards" :key="card.key" class="stat-card card-panel">
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value" :style="{ color: card.color }">
          {{ stats?.[card.key] ?? '-' }}
        </div>
      </div>
    </div>

    <div class="card-panel mt">
      <h3>流水线状态分布</h3>
      <el-empty v-if="!stats?.job_breakdown?.length" description="暂无任务记录" />
      <el-table v-else :data="stats.job_breakdown" size="small">
        <el-table-column prop="stage" label="阶段" />
        <el-table-column prop="status" label="状态" />
        <el-table-column prop="count" label="数量" width="100" />
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
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

.mt {
  margin-top: 20px;
}

h3 {
  margin: 0 0 16px;
}
</style>
