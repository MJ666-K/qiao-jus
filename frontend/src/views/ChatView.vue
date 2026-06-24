<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Close, Document, Plus } from '@element-plus/icons-vue'
import { deleteConversation, listConversations } from '@/api/conversations'
import { listReports } from '@/api/reports'
import { useConversationStore } from '@/stores/conversation'
import type { ConversationSummary, Report, SourceType } from '@/types'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const route = useRoute()
const router = useRouter()
const store = useConversationStore()

const inputText = ref('')
const reportOptions = ref<Report[]>([])
const conversations = ref<ConversationSummary[]>([])
const scrollContainer = ref<HTMLDivElement | null>(null)

const groupedConversations = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)
  const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)

  const todayConvs: ConversationSummary[] = []
  const weekConvs: ConversationSummary[] = []
  const monthConvs: ConversationSummary[] = []
  const olderConvs: ConversationSummary[] = []

  for (const conv of conversations.value) {
    const convDate = new Date(conv.updated_at)
    if (convDate >= today) {
      todayConvs.push(conv)
    } else if (convDate >= weekAgo) {
      weekConvs.push(conv)
    } else if (convDate >= monthAgo) {
      monthConvs.push(conv)
    } else {
      olderConvs.push(conv)
    }
  }

  return [
    { label: '今日', conversations: todayConvs },
    { label: '七日内', conversations: weekConvs },
    { label: '一个月内', conversations: monthConvs },
    { label: '更早', conversations: olderConvs },
  ].filter(g => g.conversations.length > 0)
})

function renderMarkdown(content: string): string {
  return marked.parse(content) as string
}

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
      if (conversationId) {
        await store.initConversation({
          conversationId,
          reportId: reportIdFromQuery,
        })
      }
    } catch (e) {
      ElMessage.error(e instanceof Error ? e.message : '会话连接失败')
    }
  }
  await refreshBoundReport()
}

async function startNewConversation() {
  try {
    const reportIdFromQuery = route.query.report_id as string | undefined
    const conv = await store.createConversationAndSet({ reportId: reportIdFromQuery })
    const summary: ConversationSummary = {
      id: conv.id,
      title: conv.title,
      report_id: conv.report_id,
      track: conv.track,
      message_count: 0,
      enable_thinking: conv.enable_thinking,
      created_at: conv.created_at,
      updated_at: conv.updated_at,
    }
    conversations.value.unshift(summary)
    router.push({ name: 'chat-with-conversation', params: { conversationId: conv.id } })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建会话失败')
  }
}

async function switchConversation(conv: ConversationSummary) {
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
    const reportIdFromQuery = route.query.report_id as string | undefined
    if (!store.currentConversation) {
      await store.initConversation({ reportId: reportIdFromQuery })
    } else {
      await store.initConversation({ conversationId: store.currentConversation.id })
    }
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
watch(() => route.params.conversationId, async (newId, oldId) => {
  if (newId !== oldId && !store.isStreaming) {
    await ensureSession()
  }
})

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
        <template v-else>
          <div v-for="group in groupedConversations" :key="group.label">
            <div class="conv-group-label">{{ group.label }}</div>
            <div
              v-for="conv in group.conversations"
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
        </template>
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
            <div class="markdown-content" v-html="renderMarkdown(m.content)"></div>
            <div v-if="m.role === 'assistant'" class="msg-meta">
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

        <div v-if="store.statusMessage && !store.streamingMessage" class="msg-row assistant">
          <div class="bubble status">
            <div class="thinking-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
            <span class="status-text">{{ store.statusMessage }}</span>
          </div>
        </div>

        <div v-if="store.streamingMessage" class="msg-row assistant">
          <div class="bubble streaming">
            <div class="markdown-content" v-html="renderMarkdown(store.streamingMessage)"></div>
            <span class="cursor">▍</span>
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
  height: 100%;
  margin: 0;
  background: #f8fafc;
  overflow: hidden;
}

.conv-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
}

.conv-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.conv-header .el-button {
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 8px;
}

.conv-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #1e293b;
}

.conv-title .el-icon {
  color: #f97316;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.conv-group-label {
  font-size: 12px;
  color: #94a3b8;
  padding: 8px 12px 4px;
  font-weight: 600;
  text-transform: uppercase;
}

.conv-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  background: transparent;
  border: none;
}

.conv-item:hover {
  background: #f8fafc;
}

.conv-item.active {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border: 1px solid #fdba74;
}

.conv-item-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 20px;
  color: #1e293b;
}

.conv-item.active .conv-item-title {
  color: #7c2d12;
}

.conv-item-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.msg-count {
  display: none;
}

.bound-icon {
  color: #f97316;
}

.del-icon {
  position: absolute;
  top: 10px;
  right: 8px;
  font-size: 14px;
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
  background: #fff;
  overflow: hidden;
}

.chat-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-label {
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
}

.report-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border-radius: 10px;
  font-size: 13px;
  color: #92400e;
  max-width: 50%;
  border: 1px solid #fcd34d;
}

.report-banner-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
  min-height: 0;
  max-height: calc(100vh - 200px);
}

.msg-row {
  display: flex;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 85%;
  padding: 6px 10px;
  border-radius: 10px;
  position: relative;
}

.msg-row.user .bubble {
  background: linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%);
  color: #7c2d12;
  border: 1px solid #fdba74;
  max-width: none;
  overflow: visible;
  max-height: none;
}

.msg-row.user .bubble::after {
  content: '';
  position: absolute;
  right: -5px;
  bottom: 6px;
  width: 10px;
  height: 10px;
  background: #fed7aa;
  border-radius: 0 0 10px 0;
  clip-path: polygon(0 0, 100% 0, 100% 100%);
}

.msg-row.assistant .bubble {
  background: #fff;
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
}

.msg-meta {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid #f1f5f9;
}

.confidence {
  margin-bottom: 12px;
}

.citations {
  margin-top: 6px;
}

.citations .el-collapse {
  border: none;
}

.citations .el-collapse-item__header {
  background: #f8fafc;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: #64748b;
  border: 1px solid #e2e8f0;
  height: 32px;
  line-height: 32px;
}

.citations .el-collapse-item__content {
  padding: 8px 0;
}

.source-item {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-left: 3px solid #3b82f6;
  padding: 8px 12px;
  margin-bottom: 6px;
  border-radius: 6px;
  transition: all 0.2s;
}

.source-item:hover {
  background: #eff6ff;
  border-left-color: #2563eb;
  transform: translateX(2px);
}

.source-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.title-text {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
}

.excerpt {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.5;
}

.suggested {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.suggested .el-button {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #93c5fd;
  color: #1e40af;
  font-weight: 500;
  font-size: 13px;
  padding: 6px 12px;
  height: auto;
  transition: all 0.2s;
}

.suggested .el-button:hover {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  border-color: #60a5fa;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 10px 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
  flex-shrink: 0;
}

.input-area .el-input {
  flex: 1;
}

.input-area .el-textarea__inner {
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  padding: 8px 10px;
  font-size: 14px;
  transition: all 0.2s;
  min-height: 40px;
}

.input-area .el-textarea__inner:focus {
  border-color: #f97316;
  box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.1);
}

.input-actions {
  flex-shrink: 0;
}

.input-actions .el-button {
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 13px;
}

.input-actions .el-button--primary {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.3);
  transition: all 0.2s;
}

.input-actions .el-button--primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(249, 115, 22, 0.4);
}

.input-actions .el-button--danger {
  border-radius: 12px;
}

.markdown-content {
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
  color: #1e293b;
}

.markdown-content p {
  margin: 0 0 6px 0;
}

.markdown-content p:last-child {
  margin-bottom: 0;
}

.markdown-content ul, .markdown-content ol {
  margin: 6px 0;
  padding-left: 18px;
}

.markdown-content li {
  margin: 2px 0;
  line-height: 1.4;
}

.markdown-content code {
  background: #fef3c7;
  color: #92400e;
  padding: 3px 8px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  border: 1px solid #fde68a;
}

.markdown-content pre {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #e2e8f0;
  padding: 16px 20px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 16px 0;
  border: 1px solid #334155;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.markdown-content pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  border: none;
}

.markdown-content h1, .markdown-content h2, .markdown-content h3 {
  margin: 20px 0 12px 0;
  font-weight: 700;
  color: #1e293b;
}

.markdown-content h1 { font-size: 22px; border-bottom: 2px solid #f97316; padding-bottom: 8px; }
.markdown-content h2 { font-size: 18px; color: #334155; }
.markdown-content h3 { font-size: 16px; }

.markdown-content a {
  color: #2563eb;
  text-decoration: none;
  border-bottom: 1px solid #93c5fd;
}

.markdown-content a:hover {
  color: #1d4ed8;
  border-bottom-color: #2563eb;
}

.markdown-content blockquote {
  border-left: 4px solid #f97316;
  background: #fff7ed;
  padding: 12px 16px;
  margin: 16px 0;
  border-radius: 8px;
  color: #7c2d12;
}

.markdown-content table {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  display: block;
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.markdown-content th, .markdown-content td {
  border: 1px solid #cbd5e1;
  padding: 12px 16px;
  text-align: left;
  min-width: 100px;
}

.markdown-content th {
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  font-weight: 700;
  color: #1e293b;
}

.markdown-content td {
  background: #fff;
}

.markdown-content tr:nth-child(even) td {
  background: #f8fafc;
}

.markdown-content tr:hover td {
  background: #fff7ed;
}

.streaming .cursor {
  animation: blink 1s infinite;
  color: #f97316;
  font-size: 18px;
  vertical-align: middle;
  margin-left: 2px;
}

.status .bubble {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border: 1px solid #fed7aa;
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 12px;
  padding: 12px 18px;
  width: fit-content;
}

.status .thinking-indicator {
  display: flex !important;
  flex-direction: row !important;
  align-items: center !important;
  gap: 4px;
  flex-shrink: 0;
}

.status .dot {
  width: 8px;
  height: 8px;
  background: #f97316;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
  flex-shrink: 0;
}

.status-text {
  flex-shrink: 0;
}

.status .dot:nth-child(1) { animation-delay: -0.32s; }
.status .dot:nth-child(2) { animation-delay: -0.16s; }
.status .dot:nth-child(3) { animation-delay: 0s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.status .status-text {
  color: #92400e;
  font-size: 14px;
  font-weight: 500;
}

.loading-bubble {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border: 1px solid #fed7aa;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  min-width: 120px;
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  background: #f97316;
  border-radius: 50%;
  animation: loading-bounce 1.4s infinite ease-in-out both;
}

.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }
.loading-dot:nth-child(3) { animation-delay: 0s; }

@keyframes loading-bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.loading-text {
  color: #92400e;
  font-size: 14px;
  font-weight: 500;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
