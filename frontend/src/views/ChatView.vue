<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Close, Document, Plus } from '@element-plus/icons-vue'
import { deleteConversation, listConversations } from '@/api/conversations'
import { listReports } from '@/api/reports'
import { useConversationStore } from '@/stores/conversation'
import type { ConversationSummary, Report, SourceType } from '@/types'

const route = useRoute()
const router = useRouter()
const store = useConversationStore()

const inputText = ref('')
const reportOptions = ref<Report[]>([])
const conversations = ref<ConversationSummary[]>([])
const scrollContainer = ref<HTMLDivElement | null>(null)

const sourceTagType: Record<SourceType, 'success' | 'warning' | 'info' | 'primary' | 'danger'> = {
  law: 'primary',
  case: 'success',
  report: 'warning',
  user_doc: 'info',
  compliance: 'primary',
  graph: 'danger',
}

const sourceTagText: Record<SourceType, string> = {
  law: '法规',
  case: '类案',
  report: '报告',
  user_doc: '材料',
  compliance: '合规',
  graph: '图谱',
}

const boundReport = ref<Report | null>(null)

async function loadConversations() {
  try {
    conversations.value = await listConversations()
  } catch {
    conversations.value = []
  }
}

async function loadReportOptions() {
  try {
    reportOptions.value = await listReports()
  } catch {
    reportOptions.value = []
  }
}

async function refreshBoundReport() {
  if (!store.boundReportId) {
    boundReport.value = null
    return
  }
  boundReport.value = reportOptions.value.find((x) => x.id === store.boundReportId) || null
}

async function ensureSession() {
  const conversationId = route.params.conversationId as string | undefined
  const reportIdFromQuery = route.query.report_id as string | undefined
  if (!store.isConnected) {
    try {
      await store.initConversation({
        conversationId,
        reportId: reportIdFromQuery,
      })
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '会话连接失败')
    }
  }
  await refreshBoundReport()
}

async function startNewConversation() {
  store.disconnect()
  router.push({ name: 'chat' })
  try {
    await store.initConversation({})
    await loadConversations()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '新建会话失败')
  }
}

async function switchConversation(conv: ConversationSummary) {
  store.disconnect()
  router.push({ name: 'chat-with-conversation', params: { conversationId: conv.id } })
  try {
    await store.initConversation({ conversationId: conv.id })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '切换会话失败')
  }
}

async function removeConversation(conv: ConversationSummary, event: Event) {
  event.stopPropagation()
  try {
    await ElMessageBox.confirm(`确认删除会话「${conv.title}」？`, '删除会话', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteConversation(conv.id)
    if (store.currentConversation?.id === conv.id) {
      store.disconnect()
      router.push({ name: 'chat' })
      await store.initConversation({})
    }
    await loadConversations()
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function send() {
  const text = inputText.value.trim()
  if (!text) return
  if (!store.isConnected) {
    await ensureSession()
    if (!store.isConnected) return
  }
  inputText.value = ''
  await store.sendMessage(text)
  await scrollToBottom()
  await loadConversations()
}

function pickSuggested(q: string) {
  inputText.value = q
  send()
}

async function onChangeReport(reportId: string | null) {
  store.bindReport(reportId)
  await refreshBoundReport()
}

async function scrollToBottom() {
  await nextTick()
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
  }
}

watch(() => store.streamingMessage, () => scrollToBottom())
watch(() => store.messages.length, () => scrollToBottom())
watch(() => store.boundReportId, () => refreshBoundReport())

onMounted(async () => {
  await Promise.all([loadConversations(), loadReportOptions()])
  await ensureSession()
})

onUnmounted(() => {
  store.disconnect()
})
</script>

<template>
  <div class="chat-page">
    <aside class="conv-sidebar">
      <div class="conv-header">
        <span class="conv-title">
          <el-icon><ChatDotRound /></el-icon>
          会话
        </span>
        <el-button type="primary" size="small" :icon="Plus" @click="startNewConversation">
          新建
        </el-button>
      </div>
      <div class="conv-list">
        <el-empty v-if="!conversations.length" :image-size="60" description="暂无会话" />
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: store.currentConversation?.id === conv.id }"
          @click="switchConversation(conv)"
        >
          <div class="conv-item-title">{{ conv.title }}</div>
          <div class="conv-item-meta">
            <span>{{ new Date(conv.updated_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
            <span v-if="conv.message_count" class="msg-count">{{ conv.message_count }} 条</span>
            <el-icon v-if="conv.report_id" class="bound-icon" title="已绑定报告">
              <Document />
            </el-icon>
          </div>
          <el-icon class="del-icon" @click="removeConversation(conv, $event)">
            <Close />
          </el-icon>
        </div>
      </div>
    </aside>

    <div class="chat-main">
      <div class="chat-toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">绑定报告：</span>
          <el-select
            :model-value="store.boundReportId"
            placeholder="不绑定（通用问答）"
            clearable
            size="small"
            style="width: 280px"
            @change="onChangeReport"
          >
            <el-option
              v-for="r in reportOptions"
              :key="r.id"
              :label="`${r.type} · ${(r.summary || r.id.slice(0, 8)).slice(0, 30)}`"
              :value="r.id"
            />
          </el-select>
          <el-tag v-if="store.isConnected" type="success" size="small">已连接</el-tag>
          <el-tag v-else type="info" size="small">未连接</el-tag>
        </div>
        <div v-if="boundReport" class="report-banner">
          <el-tag type="warning" size="small">
            报告 {{ boundReport.confidence }}%
          </el-tag>
          <span class="report-banner-text">{{ boundReport.summary?.slice(0, 50) || boundReport.type }}</span>
        </div>
      </div>

      <div ref="scrollContainer" class="messages">
        <el-empty v-if="!store.messages.length && !store.streamingMessage" description="开始提问吧，例如：合同第2条风险怎么改？" />

        <div
          v-for="m in store.messages"
          :key="m.id"
          class="msg-row"
          :class="m.role"
        >
          <div class="bubble">
            <pre class="text-pre">{{ m.content }}</pre>
            <div v-if="m.role === 'assistant'" class="msg-meta">
              <span v-if="m.confidence != null" class="confidence">
                置信度 {{ m.confidence }}
              </span>
              <div v-if="m.citations.length" class="citations">
                <el-collapse>
                  <el-collapse-item :title="`引用来源 (${m.citations.length})`">
                    <div
                      v-for="(c, i) in m.citations"
                      :key="i"
                      class="source-item"
                    >
                      <div class="source-title">
                        <el-tag :type="sourceTagType[c.source_type]" size="small">
                          {{ sourceTagText[c.source_type] }}
                        </el-tag>
                        <span class="title-text">{{ c.source_title }}</span>
                      </div>
                      <pre v-if="c.excerpt" class="text-pre excerpt">{{ c.excerpt }}</pre>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <div v-if="m.suggested_questions.length" class="suggested">
                <el-button
                  v-for="(q, i) in m.suggested_questions"
                  :key="i"
                  size="small"
                  round
                  @click="pickSuggested(q)"
                >
                  {{ q }}
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="store.streamingMessage" class="msg-row assistant">
          <div class="bubble streaming">
            <pre class="text-pre">{{ store.streamingMessage }}<span class="cursor">▍</span></pre>
          </div>
        </div>
      </div>

      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :disabled="store.isStreaming"
          placeholder="输入问题，Ctrl+Enter 发送"
          resize="none"
          @keyup.ctrl.enter="send"
        />
        <div class="input-actions">
          <el-button
            v-if="store.isStreaming"
            type="danger"
            @click="store.stopGeneration()"
          >
            停止生成
          </el-button>
          <el-button v-else type="primary" :disabled="!inputText.trim()" @click="send">
            发送
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: calc(100vh - 130px);
  margin: -24px -28px -24px -28px;
}

.conv-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  flex-direction: column;
  padding: 14px 10px;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
}

.conv-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #1e293b;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.conv-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.conv-item:hover {
  background: #fafaf9;
}

.conv-item.active {
  background: #ffedd5;
  color: #9a3412;
}

.conv-item-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 20px;
}

.conv-item-meta {
  font-size: 11px;
  color: #64748b;
  margin-top: 4px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.msg-count {
  color: #94a3b8;
}

.bound-icon {
  color: #d97706;
}

.del-icon {
  position: absolute;
  top: 10px;
  right: 8px;
  font-size: 12px;
  color: #cbd5e1;
  opacity: 0;
  transition: all 0.15s;
}

.conv-item:hover .del-icon {
  opacity: 1;
}

.del-icon:hover {
  color: #ef4444;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-label {
  color: #475569;
  font-size: 13px;
}

.report-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #fef3c7;
  border-radius: 6px;
  font-size: 12px;
  color: #92400e;
  max-width: 50%;
}

.report-banner-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.msg-row {
  display: flex;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f8fafc;
}

.msg-row.user .bubble {
  background: #ffedd5;
  color: #9a3412;
}

.msg-row.assistant .bubble {
  background: #fff;
  border: 1px solid #e2e8f0;
}

.bubble .text-pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.6;
}

.streaming .cursor {
  animation: blink 1s infinite;
  color: #f97316;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.msg-meta {
  margin-top: 8px;
  font-size: 12px;
}

.confidence {
  color: #64748b;
  margin-right: 8px;
}

.citations {
  margin-top: 6px;
}

.source-item {
  border-left: 2px solid #cbd5e1;
  padding: 4px 10px;
  margin-bottom: 8px;
}

.source-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.title-text {
  font-weight: 600;
  font-size: 13px;
}

.excerpt {
  font-size: 12px;
  color: #475569;
  margin: 0;
}

.suggested {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 10px 16px 14px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.input-area .el-input {
  flex: 1;
}

.input-actions {
  flex-shrink: 0;
}
</style>
