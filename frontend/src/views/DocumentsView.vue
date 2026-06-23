<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import { useReportsStore } from '@/stores/reports'
import DocStatusTag from '@/components/DocStatusTag.vue'
import { docTypeLabel } from '@/constants/docTypes'
import type { Dataset, DocumentItem, ReportType } from '@/types'

const router = useRouter()
const reportsStore = useReportsStore()
const loading = ref(false)
const datasets = ref<Dataset[]>([])
const documents = ref<DocumentItem[]>([])
const activeTab = ref<'user' | 'platform'>('user')
const datasetFilter = ref('')
const docTypeFilter = ref('')
const uploadDocType = ref('law')
let pollTimer: ReturnType<typeof setInterval> | null = null

const DOC_TYPE_TO_REPORT_TYPE: Record<string, ReportType> = {
  contract: 'contract_review',
  dispute: 'dispute_analysis',
}

const PLATFORM_DOC_TYPES = ['law', 'case', 'compliance']
const USER_DOC_TYPES = ['contract', 'dispute', 'report']

const filteredDocuments = computed(() => {
  return documents.value.filter((d) => {
    const dt = String(d.metadata?.doc_type || '')
    if (activeTab.value === 'platform' && !PLATFORM_DOC_TYPES.includes(dt)) return false
    if (activeTab.value === 'user' && !USER_DOC_TYPES.includes(dt)) return false
    return true
  })
})

const filteredDatasets = computed(() => {
  return datasets.value.filter((ds) => {
    const dt = String(ds.metadata?.doc_type || '')
    if (activeTab.value === 'platform' && !PLATFORM_DOC_TYPES.includes(dt)) return false
    if (activeTab.value === 'user' && !USER_DOC_TYPES.includes(dt)) return false
    return true
  })
})

async function loadDatasets() {
  datasets.value = await listDatasets()
}

async function onDatasetChange(id: string) {
  const ds = datasets.value.find((d) => d.id === id)
  uploadDocType.value = String(ds?.metadata?.doc_type || 'law')
  await loadDocuments()
}

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await listDocuments({
      ...(datasetFilter.value ? { dataset_id: datasetFilter.value } : {}),
      ...(docTypeFilter.value ? { doc_type: docTypeFilter.value } : {}),
    })
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
    const ds = datasets.value.find((d) => d.id === datasetFilter.value)
    const dt = String(ds?.metadata?.doc_type || uploadDocType.value)
    const doc = await uploadDocument(file, datasetFilter.value, dt)
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

async function generateReport(doc: DocumentItem) {
  const dt = String(doc.metadata?.doc_type || '')
  const reportType = DOC_TYPE_TO_REPORT_TYPE[dt]
  if (!reportType) {
    ElMessage.warning('该文档类型暂不支持自动分析')
    return
  }
  try {
    const r = await reportsStore.triggerAnalyze(doc.id, reportType)
    ElMessage.success('已触发报告生成')
    router.push({ name: 'report-view', params: { id: r.id } })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '触发分析失败')
  }
}

function isPlatformDoc(row: DocumentItem): boolean {
  return PLATFORM_DOC_TYPES.includes(String(row.metadata?.doc_type || ''))
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
    <p class="page-desc">
      切换「我的文档」（用户私有：合同/纠纷/报告）与「公共法规库」（平台共享：法规/类案/合规）。用户文档可生成分析报告。
    </p>

    <el-tabs v-model="activeTab" class="library-tabs">
      <el-tab-pane label="我的文档（用户私有）" name="user" />
      <el-tab-pane label="公共法规库（只读）" name="platform" />
    </el-tabs>

    <div class="toolbar">
      <el-select
        v-model="datasetFilter"
        placeholder="筛选知识库"
        clearable
        @change="onDatasetChange"
      >
        <el-option
          v-for="ds in filteredDatasets"
          :key="ds.id"
          :label="ds.name"
          :value="ds.id"
        />
      </el-select>
      <el-select
        v-if="activeTab === 'platform'"
        v-model="docTypeFilter"
        placeholder="文档类型"
        clearable
        style="width: 140px"
        @change="loadDocuments"
      >
        <el-option label="法规" value="law" />
        <el-option label="类案" value="case" />
        <el-option label="合规" value="compliance" />
      </el-select>
      <el-select
        v-else
        v-model="docTypeFilter"
        placeholder="文档类型"
        clearable
        style="width: 140px"
        @change="loadDocuments"
      >
        <el-option label="合同" value="contract" />
        <el-option label="纠纷" value="dispute" />
        <el-option label="报告" value="report" />
      </el-select>
    </div>

    <el-upload
      v-if="activeTab === 'user'"
      class="upload-area card-panel"
      drag
      :auto-upload="true"
      :show-file-list="false"
      :before-upload="onUpload"
      accept=".md,.txt,.pdf,.docx,.html"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽合同/纠纷材料到此处，或 <em>点击上传</em>（自动入用户私有库）</div>
      <template #tip>
        <div class="el-upload__tip">支持 .md / .txt / .pdf / .docx / .html；上传后自动 parse → chunk → embed → graph</div>
      </template>
    </el-upload>

    <div v-loading="loading" class="card-panel mt">
      <el-empty
        v-if="!filteredDocuments.length"
        :description="activeTab === 'user' ? '尚未上传用户文档' : '公共法规库为空，请联系管理员上传'"
      />
      <el-table v-else :data="filteredDocuments" stripe>
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="isPlatformDoc(row) ? 'primary' : 'success'" size="small">
              {{ docTypeLabel(String(row.metadata?.doc_type || '')) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="库" width="90">
          <template #default="{ row }">
            <el-tag :type="isPlatformDoc(row) ? 'info' : 'warning'" size="small" effect="plain">
              {{ isPlatformDoc(row) ? '公共' : '私有' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <DocStatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="290" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'done' && (row.metadata?.doc_type === 'contract' || row.metadata?.doc_type === 'dispute')"
              link
              type="success"
              @click="generateReport(row)"
            >
              生成报告
            </el-button>
            <el-button link type="primary" @click="showDetail(row.id)">详情</el-button>
            <el-button link @click="router.push(`/documents/${row.id}/chunks`)">文本块</el-button>
            <template v-if="!isPlatformDoc(row)">
              <el-button link @click="reindex(row.id)">重建</el-button>
              <el-button link type="danger" @click="remove(row.id)">删除</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.library-tabs {
  margin-bottom: 12px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
}

.upload-area {
  margin-bottom: 16px;
}

.upload-icon {
  font-size: 48px;
  color: #f97316;
}

.mt {
  margin-top: 16px;
}
</style>
