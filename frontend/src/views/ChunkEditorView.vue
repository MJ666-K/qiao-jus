<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteChunk, listChunks, updateChunk, type ChunkItem } from '@/api/chunks'
import { getDocument } from '@/api/documents'
import type { DocumentItem } from '@/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const doc = ref<DocumentItem | null>(null)
const chunks = ref<ChunkItem[]>([])
const editingId = ref<string | null>(null)
const editText = ref('')
const searchQuery = ref('')

const filteredChunks = () => {
  if (!searchQuery.value.trim()) return chunks.value
  const q = searchQuery.value.toLowerCase()
  return chunks.value.filter((c) => c.text.toLowerCase().includes(q))
}

async function loadData() {
  loading.value = true
  try {
    const [d, c] = await Promise.all([
      getDocument(route.params.id as string),
      listChunks(route.params.id as string),
    ])
    doc.value = d
    chunks.value = c
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function startEdit(c: ChunkItem) {
  editingId.value = c.id
  editText.value = c.text
}

function cancelEdit() {
  editingId.value = null
  editText.value = ''
}

async function saveEdit(c: ChunkItem) {
  if (!editText.value.trim()) {
    ElMessage.warning('文本不能为空')
    return
  }
  saving.value = true
  try {
    const updated = await updateChunk(c.document_id, c.id, editText.value, true)
    const idx = chunks.value.findIndex((x) => x.id === c.id)
    if (idx >= 0) chunks.value[idx] = updated
    editingId.value = null
    ElMessage.success('已保存并重新向量化')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeChunk(c: ChunkItem) {
  try {
    await ElMessageBox.confirm(`确认删除该文本块？此操作不可逆。`, '删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteChunk(c.document_id, c.id)
    chunks.value = chunks.value.filter((x) => x.id !== c.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

function tagType(scope: string) {
  return scope === 'user' ? 'warning' : 'info'
}

function back() {
  router.push('/documents')
}

onMounted(loadData)
</script>

<template>
  <div v-loading="loading">
    <div class="header-row">
      <div>
        <h2 class="page-title">文本块管理</h2>
        <p class="page-desc">
          {{ doc?.title }} — 共 {{ chunks.length }} 个文本块。支持查看、编辑（自动重新向量化）、删除。
        </p>
      </div>
      <el-button @click="back">返回文档列表</el-button>
    </div>

    <div class="card-panel toolbar">
      <el-input
        v-model="searchQuery"
        placeholder="在文本块中搜索..."
        clearable
        style="width: 300px"
      />
      <el-tag>共 {{ filteredChunks().length }} 块</el-tag>
    </div>

    <el-empty v-if="!chunks.length && !loading" description="该文档暂无文本块（可能还在处理中）" />

    <div class="chunk-list">
      <div
        v-for="c in filteredChunks()"
        :key="c.id"
        class="chunk-card card-panel"
      >
        <div class="chunk-header">
          <div class="chunk-meta">
            <el-tag size="small" :type="tagType(c.scope)">{{ c.scope === 'user' ? '私有' : '公共' }}</el-tag>
            <span class="chunk-index">#{{ c.chunk_index }}</span>
            <span v-if="c.char_count" class="chunk-chars">{{ c.char_count }} 字</span>
          </div>
          <div class="chunk-actions">
            <template v-if="editingId === c.id">
              <el-button size="small" type="primary" :loading="saving" @click="saveEdit(c)">保存</el-button>
              <el-button size="small" @click="cancelEdit">取消</el-button>
            </template>
            <template v-else>
              <el-button size="small" link @click="startEdit(c)">编辑</el-button>
              <el-button size="small" link type="danger" @click="removeChunk(c)">删除</el-button>
            </template>
          </div>
        </div>

        <div v-if="editingId === c.id" class="chunk-edit">
          <el-input
            v-model="editText"
            type="textarea"
            :rows="6"
            placeholder="编辑文本块内容"
          />
        </div>
        <pre v-else class="chunk-text">{{ c.text }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 16px;
}

.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chunk-card {
  padding: 14px 16px;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

.chunk-index {
  font-weight: 600;
}

.chunk-chars {
  color: #94a3b8;
}

.chunk-actions {
  display: flex;
  gap: 4px;
}

.chunk-text {
  font-size: 14px;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}

.chunk-edit {
  margin-top: 4px;
}
</style>
