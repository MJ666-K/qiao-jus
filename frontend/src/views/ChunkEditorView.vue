<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, EditPen, Search } from '@element-plus/icons-vue'
import { deleteChunk, listChunks, updateChunk, type ChunkItem } from '@/api/chunks'
import { getDocument } from '@/api/documents'
import DocStatusTag from '@/components/DocStatusTag.vue'
import { docTypeLabel } from '@/constants/docTypes'
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
const expandedIds = ref<Set<string>>(new Set())

const filteredChunks = computed(() => {
  if (!searchQuery.value.trim()) return chunks.value
  const q = searchQuery.value.toLowerCase()
  return chunks.value.filter((c) => c.text.toLowerCase().includes(q))
})

const totalChars = computed(() =>
  chunks.value.reduce((sum, c) => sum + (c.char_count || c.text.length), 0),
)

function fileExt(title: string): string {
  const m = title.match(/\.([^.]+)$/i)
  if (!m) return 'FILE'
  const ext = m[1].toUpperCase()
  return ext.length > 4 ? ext.slice(0, 4) : ext
}

function fileExtClass(title: string): string {
  const ext = (title.split('.').pop() || '').toLowerCase()
  if (ext === 'pdf') return 'ext-pdf'
  if (ext === 'docx' || ext === 'doc') return 'ext-doc'
  if (ext === 'md') return 'ext-md'
  if (ext === 'html' || ext === 'htm') return 'ext-html'
  if (ext === 'txt') return 'ext-txt'
  return 'ext-default'
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

function isExpanded(id: string) {
  return expandedIds.value.has(id)
}

function toggleExpand(id: string) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

function startEdit(c: ChunkItem) {
  editingId.value = c.id
  editText.value = c.text
  expandedIds.value = new Set([...expandedIds.value, c.id])
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
    await ElMessageBox.confirm('确认删除该文本块？此操作不可逆。', '删除', { type: 'warning' })
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

function back() {
  router.push('/documents')
}

onMounted(loadData)
</script>

<template>
  <div class="chunk-page">
    <div v-loading="loading" class="workspace card-panel">
      <!-- 紧凑顶栏：一行搞定导航 + 文档信息 + 搜索 -->
      <header v-if="doc" class="top-bar">
        <div class="top-left">
          <button type="button" class="back-btn" @click="back">
            <el-icon><ArrowLeft /></el-icon>
          </button>
          <div class="file-badge" :class="fileExtClass(doc.title)">{{ fileExt(doc.title) }}</div>
          <div class="doc-brief">
            <h1 class="doc-name">{{ doc.title }}</h1>
            <div class="doc-tags">
              <DocStatusTag :status="doc.status" />
              <span class="tag">{{ docTypeLabel(String(doc.metadata?.doc_type || '')) }}</span>
              <span class="tag muted">{{ doc.scope === 'user' ? '私有' : '公共' }}</span>
              <span class="tag stat">{{ chunks.length }} 块</span>
              <span class="tag stat">{{ totalChars.toLocaleString() }} 字</span>
            </div>
          </div>
        </div>
        <div class="top-right">
          <el-input
            v-model="searchQuery"
            placeholder="搜索文本块..."
            clearable
            :prefix-icon="Search"
            class="search-input"
          />
        </div>
      </header>

      <!-- 列表区 -->
      <div class="list-area">
        <el-empty v-if="!chunks.length && !loading" description="暂无文本块，文档可能还在处理中" />

        <template v-else>
          <div v-if="filteredChunks.length === 0" class="no-match">没有匹配的文本块</div>

          <article
            v-for="c in filteredChunks"
            :key="c.id"
            class="chunk-card"
            :class="{ editing: editingId === c.id, expanded: isExpanded(c.id) }"
          >
            <div class="chunk-header">
              <div class="chunk-meta">
                <span class="chunk-idx">#{{ c.chunk_index }}</span>
                <span class="scope-badge" :class="c.scope === 'user' ? 'private' : 'public'">
                  {{ c.scope === 'user' ? '私有' : '公共' }}
                </span>
                <span class="char-count">{{ c.char_count || c.text.length }} 字</span>
              </div>
              <div class="chunk-actions">
                <template v-if="editingId === c.id">
                  <el-button size="small" type="primary" :loading="saving" @click="saveEdit(c)">
                    保存
                  </el-button>
                  <el-button size="small" @click="cancelEdit">取消</el-button>
                </template>
                <template v-else>
                  <button type="button" class="act-btn" @click="startEdit(c)">
                    <el-icon><EditPen /></el-icon>编辑
                  </button>
                  <button type="button" class="act-btn danger" @click="removeChunk(c)">
                    <el-icon><Delete /></el-icon>删除
                  </button>
                  <button
                    v-if="c.text.length > 300"
                    type="button"
                    class="act-btn ghost"
                    @click="toggleExpand(c.id)"
                  >
                    {{ isExpanded(c.id) ? '收起' : '展开' }}
                  </button>
                </template>
              </div>
            </div>

            <div class="chunk-body">
              <el-input
                v-if="editingId === c.id"
                v-model="editText"
                type="textarea"
                :autosize="{ minRows: 8, maxRows: 24 }"
                class="chunk-editor"
                placeholder="编辑文本块内容"
              />
              <div
                v-else
                class="chunk-text"
                :class="{ 'chunk-text--expanded': isExpanded(c.id) }"
              >
                {{ c.text }}
              </div>
            </div>
          </article>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chunk-page {
  height: calc(100vh - var(--topbar-height) - var(--page-padding-y) * 2);
  min-height: 420px;
  min-width: 0;
}

.workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: var(--brand-surface);
}

/* ---- 顶栏 ---- */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border-subtle);
  background: linear-gradient(180deg, #fffbf5 0%, var(--brand-surface) 100%);
  flex-shrink: 0;
}

.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.back-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: #fff;
  color: var(--text-muted);
  display: grid;
  place-items: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.back-btn:hover {
  color: var(--brand-primary);
  border-color: rgb(249 115 22 / 30%);
  background: var(--brand-primary-soft);
}

.file-badge {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 10px;
  font-weight: 800;
  flex-shrink: 0;
  border: 1px solid transparent;
}

.file-badge.ext-pdf { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
.file-badge.ext-doc { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }
.file-badge.ext-md { background: #ecfdf5; color: #059669; border-color: #a7f3d0; }
.file-badge.ext-html { background: #fff7ed; color: #ea580c; border-color: #fed7aa; }
.file-badge.ext-txt { background: #f5f5f4; color: #57534e; border-color: #e7e5e4; }
.file-badge.ext-default { background: var(--brand-primary-soft); color: var(--brand-primary-dark); border-color: rgb(249 115 22 / 20%); }

.doc-brief {
  min-width: 0;
}

.doc-name {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
  background: #f5f5f4;
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
  white-space: nowrap;
}

.tag.muted { color: var(--text-muted); }
.tag.stat { color: var(--brand-primary-dark); background: var(--brand-primary-soft); border-color: rgb(249 115 22 / 15%); }

.top-right {
  flex-shrink: 0;
}

.search-input {
  width: 220px;
}

/* ---- 列表 ---- */
.list-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px 18px 18px;
  background: #fafaf9;
}

.no-match {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
  font-size: 14px;
}

.chunk-card {
  background: var(--brand-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.chunk-card:last-child {
  margin-bottom: 0;
}

.chunk-card:hover {
  border-color: rgb(249 115 22 / 20%);
  box-shadow: var(--shadow-sm);
}

.chunk-card.editing {
  border-color: var(--brand-primary);
  box-shadow: 0 0 0 3px rgb(249 115 22 / 12%);
}

.chunk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #fff;
  border-bottom: 1px solid var(--border-subtle);
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.chunk-idx {
  font-size: 13px;
  font-weight: 700;
  color: var(--brand-primary-dark);
  min-width: 28px;
}

.scope-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}

.scope-badge.private {
  background: var(--brand-primary-soft);
  color: var(--brand-primary-dark);
}

.scope-badge.public {
  background: #f5f5f4;
  color: var(--text-secondary);
}

.char-count {
  font-size: 12px;
  color: var(--text-muted);
}

.chunk-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.act-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: #fff;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.act-btn:hover {
  color: var(--brand-primary-dark);
  border-color: rgb(249 115 22 / 25%);
  background: var(--brand-primary-soft);
}

.act-btn.danger:hover {
  color: #dc2626;
  border-color: #fecaca;
  background: #fef2f2;
}

.act-btn.ghost {
  border-color: transparent;
  background: transparent;
  color: var(--text-muted);
}

.act-btn.ghost:hover {
  background: #f5f5f4;
  color: var(--text-primary);
}

/* ---- 正文区：默认可见 + 限高滚动 ---- */
.chunk-body {
  padding: 0;
}

.chunk-text {
  display: block;
  max-height: 180px;
  overflow-y: auto;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  background: #fafaf9;
}

.chunk-text--expanded {
  max-height: none;
}

.chunk-editor :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  box-shadow: none;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.75;
  background: #fffbf5;
  resize: vertical;
  min-height: 160px;
}

.chunk-editor :deep(.el-textarea__inner:focus) {
  box-shadow: none;
  background: #fff;
}

@media (max-width: 768px) {
  .chunk-page {
    height: auto;
    min-height: 0;
  }

  .top-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    width: 100%;
  }

  .chunk-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chunk-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .chunk-text {
    max-height: 160px;
  }
}
</style>
