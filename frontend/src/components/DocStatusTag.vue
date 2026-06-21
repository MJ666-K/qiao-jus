<script setup lang="ts">
import { computed } from 'vue'
import type { DocStatus } from '@/types'

const props = defineProps<{ status: string }>()

const map: Record<DocStatus, { label: string; type: 'info' | 'success' | 'warning' | 'danger' }> = {
  pending: { label: '待处理', type: 'info' },
  parsing: { label: '解析中', type: 'info' },
  chunking: { label: '切分中', type: 'info' },
  embedding: { label: '向量化', type: 'warning' },
  graphing: { label: '建图', type: 'warning' },
  done: { label: '完成', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}

const meta = computed(() => map[props.status as DocStatus] || { label: props.status, type: 'info' as const })
</script>

<template>
  <el-tag :type="meta.type" size="small">{{ meta.label }}</el-tag>
</template>
