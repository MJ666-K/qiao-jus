import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { WsChatClient } from '@/api/ws'
import { createConversation, getConversation } from '@/api/conversations'
import type {
  ChatMessage,
  Citation,
  Conversation,
  WsServerMessage,
} from '@/types'

export const useConversationStore = defineStore('conversation', () => {
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streamingMessage = ref<string>('')
  const isStreaming = ref(false)
  const isConnected = ref(false)
  const boundReportId = ref<string | null>(null)
  const error = ref<string | null>(null)
  const pendingCitations = ref<Citation[]>([])

  let client: WsChatClient | null = null

  async function initConversation(opts: { conversationId?: string; reportId?: string } = {}) {
    error.value = null
    if (client) {
      client.close()
      client = null
    }

    if (opts.conversationId) {
      const conv = await getConversation(opts.conversationId)
      currentConversation.value = conv
      messages.value = conv.messages
      boundReportId.value = conv.report_id || null
    } else {
      const conv = await createConversation({
        title: '新对话',
        report_id: opts.reportId,
      })
      currentConversation.value = conv
      messages.value = []
      boundReportId.value = conv.report_id || null
    }

    client = new WsChatClient()
    client.onMessage(handleServerMessage)
    client.onClose(() => {
      isConnected.value = false
    })
    await client.connect()
    isConnected.value = true
    client.send({
      type: 'init',
      conversation_id: currentConversation.value?.id,
      report_id: boundReportId.value || undefined,
    })
  }

  function handleServerMessage(msg: WsServerMessage) {
    switch (msg.type) {
      case 'connected':
        if (currentConversation.value) {
          currentConversation.value.id = msg.session_id
        }
        if (msg.report_id !== undefined) {
          boundReportId.value = msg.report_id
        }
        break
      case 'token':
        streamingMessage.value += msg.content
        break
      case 'citation':
        pendingCitations.value.push({
          chunk_id: msg.chunk_id,
          document_id: msg.document_id,
          source_type: msg.source_type,
          source_title: msg.source_title,
          excerpt: msg.excerpt,
          page: msg.page,
        })
        break
      case 'done':
        messages.value.push({
          id: msg.message_id,
          role: 'assistant',
          content: streamingMessage.value,
          confidence: msg.confidence,
          suggested_questions: msg.suggested_questions || [],
          citations: msg.citations && msg.citations.length ? msg.citations : [...pendingCitations.value],
          created_at: new Date().toISOString(),
        })
        streamingMessage.value = ''
        pendingCitations.value = []
        isStreaming.value = false
        break
      case 'report_bound':
        boundReportId.value = msg.report_id || null
        break
      case 'error':
        error.value = msg.message
        isStreaming.value = false
        streamingMessage.value = ''
        pendingCitations.value = []
        ElMessage.error(msg.message)
        break
    }
  }

  async function sendMessage(content: string) {
    if (!client || !isConnected.value) {
      ElMessage.warning('会话未连接，正在重连...')
      await initConversation({ reportId: boundReportId.value || undefined })
    }
    if (!content.trim()) return
    if (isStreaming.value) {
      ElMessage.warning('正在生成中，请先停止或等待')
      return
    }

    messages.value.push({
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      suggested_questions: [],
      citations: [],
      created_at: new Date().toISOString(),
    })
    streamingMessage.value = ''
    pendingCitations.value = []
    isStreaming.value = true
    error.value = null

    try {
      client!.send({ type: 'message', content })
    } catch (e) {
      isStreaming.value = false
      error.value = e instanceof Error ? e.message : '发送失败'
      ElMessage.error(error.value!)
    }
  }

  function stopGeneration() {
    if (client && isConnected.value && isStreaming.value) {
      client.send({ type: 'stop' })
    }
  }

  function bindReport(reportId: string | null) {
    if (!client || !isConnected.value) {
      ElMessage.warning('会话未连接')
      return
    }
    client.send({ type: 'bind_report', report_id: reportId || undefined })
  }

  function disconnect() {
    if (client) {
      client.close()
      client = null
    }
    isConnected.value = false
    isStreaming.value = false
  }

  return {
    currentConversation,
    messages,
    streamingMessage,
    isStreaming,
    isConnected,
    boundReportId,
    error,
    initConversation,
    sendMessage,
    stopGeneration,
    bindReport,
    disconnect,
  }
})
