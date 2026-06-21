<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { listDatasets } from '@/api/datasets'
import {
  deleteDocument,
  getDocument,
  listDocuments,
  reindexDocument,
  uploadDocument,
} from '@/api/documents'
import DocStatusTag from '@/components/DocStatusTag.vue'
import type { Dataset, DocumentItem } from '@/types'

const loading = ref(false)
const datasets = ref<Dataset[]>([])
const documents = ref<DocumentItem[]>([])
const datasetFilter = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadDatasets() {
  datasets.value = await listDatasets()
}

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await listDocuments(
      datasetFilter.value ? { dataset_id: datasetFilter.value } : undefined,
    )
  } finally {
    loading.value = false
  }
}

async function onUpload(file: File) {
  if (!datasetFilter.value) {
    ElMessage.warning('请先选择目标知识库')
    return false
  }
  try {
    const doc = await uploadDocument(file, datasetFilter.value)
    ElMessage.success(`已上传：${doc.title}`)
    await loadDocuments()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  }
  return false
}

async function showDetail(id: string) {
  const doc = await getDocument(id)
  ElMessageBox.alert(
    `状态：${doc.status}${doc.error ? `\n错误：${doc.error}` : ''}`,
    doc.title,
  )
}

async function reindex(id: string) {
  await ElMessageBox.confirm('将清空并重建该文档的 chunks/向量/图谱，确认？', '重新索引', {
    type: 'warning',
  })
  const r = await reindexDocument(id)
  ElMessage.success(r.message || '已触发重新索引')
  await loadDocuments()
}

async function remove(id: string) {
  await ElMessageBox.confirm('删除文档及其所有 chunks/向量/图谱，确认？', '删除', {
    type: 'warning',
  })
  await deleteDocument(id)
  ElMessage.success('已删除')
  await loadDocuments()
}

onMounted(async () => {
  await loadDatasets()
  await loadDocuments()
  pollTimer = setInterval(loadDocuments, 8000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div>
    <div class="toolbar">
      <p class="page-desc">上传法规、类案、合同等材料，自动走 parse → chunk → embed → graph 流水线</p>
      <el-select v-model="datasetFilter" placeholder="选择知识库" clearable @change="loadDocuments">
        <el-option v-for="ds in datasets" :key="ds.id" :label="ds.name" :value="ds.id" />
      </el-select>
    </div>

    <el-upload
      class="upload-area card-panel"
      drag
      :auto-upload="true"
      :show-file-list="false"
      :before-upload="onUpload"
      accept=".md,.txt,.pdf,.docx,.html"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
      <template #tip>
        <div class="el-upload__tip">支持 .md / .txt / .pdf / .docx / .html，需先选择知识库</div>
      </template>
    </el-upload>

    <div v-loading="loading" class="card-panel mt">
      <el-empty v-if="!documents.length" description="暂无文档" />
      <el-table v-else :data="documents" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <DocStatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="mime_type" label="类型" width="140" />
        <el-table-column label="上传时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="showDetail(row.id)">详情</el-button>
            <el-button link @click="reindex(row.id)">重建</el-button>
            <el-button link type="danger" @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.upload-area {
  margin-bottom: 16px;
}

.upload-icon {
  font-size: 48px;
  color: #2563eb;
}

.mt {
  margin-top: 16px;
}
</style>
