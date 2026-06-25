import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { WsChatClient } from '@/api/ws'
import { createConversation, getConversation, updateConversation } from '@/api/conversations'
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
  const statusMessage = ref<string>('')
  const isStreaming = ref(false)
  const isConnected = ref(false)
  const error = ref<string | null>(null)
  const pendingCitations = ref<Citation[]>([])
  const enableThinking = ref(true)

  let client: WsChatClient | null = null

  async function connectWs() {
    if (client) {
      client.close()
      client = null
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
    })
  }

  async function initConversation(opts: {
    conversationId?: string
    reportIds?: string[]
    datasetIds?: string[]
  } = {}) {
    error.value = null

    if (opts.conversationId) {
      const conv = await getConversation(opts.conversationId)
      currentConversation.value = conv
      messages.value = conv.messages
      enableThinking.value = conv.enable_thinking ?? true
    } else {
      const conv = await createConversation({
        title: '新对话',
        report_ids: opts.reportIds || [],
        dataset_ids: opts.datasetIds || [],
        enable_thinking: enableThinking.value,
      })
      currentConversation.value = conv
      messages.value = []
      enableThinking.value = conv.enable_thinking ?? true
    }

    if (client && isConnected.value) {
      client.send({
        type: 'init',
        conversation_id: currentConversation.value?.id,
      })
      return
    }

    await connectWs()
  }

  function handleServerMessage(msg: WsServerMessage) {
    switch (msg.type) {
      case 'connected':
        if (currentConversation.value) {
          currentConversation.value.id = msg.session_id
          if (msg.dataset_ids) {
            currentConversation.value.dataset_ids = msg.dataset_ids
          }
          if (msg.report_ids) {
            currentConversation.value.report_ids = msg.report_ids
          }
        }
        break
      case 'status':
        statusMessage.value = msg.content
        break
      case 'token':
        statusMessage.value = ''
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
          content: msg.content || streamingMessage.value,
          confidence: msg.confidence,
          suggested_questions: msg.suggested_questions || [],
          citations: msg.citations && msg.citations.length ? msg.citations : [...pendingCitations.value],
          created_at: new Date().toISOString(),
        })
        streamingMessage.value = ''
        statusMessage.value = ''
        pendingCitations.value = []
        isStreaming.value = false
        break
      case 'error':
        error.value = msg.message
        isStreaming.value = false
        streamingMessage.value = ''
        statusMessage.value = ''
        pendingCitations.value = []
        ElMessage.error(msg.message)
        break
    }
  }

  async function sendMessage(content: string) {
    if (!client || !isConnected.value) {
      ElMessage.warning('会话未连接，正在重连...')
      await initConversation({
        conversationId: currentConversation.value?.id,
      })
    }
    if (!content.trim()) return
    if (isStreaming.value) {
      ElMessage.warning('正在生成中，请先停止或等待')
      return
    }

    const isFirstMessage = messages.value.length === 0

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

    if (isFirstMessage && currentConversation.value) {
      const title = content.slice(0, 30) + (content.length > 30 ? '...' : '')
      try {
        const updated = await updateConversation(currentConversation.value.id, { title })
        currentConversation.value = updated
      } catch (e) {
        console.error('Failed to update conversation title:', e)
      }
    }

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

  function disconnect() {
    if (client) {
      client.close()
      client = null
    }
    isConnected.value = false
    isStreaming.value = false
  }

  async function toggleThinking(enabled: boolean) {
    enableThinking.value = enabled
    if (currentConversation.value) {
      try {
        const updated = await updateConversation(currentConversation.value.id, {
          enable_thinking: enabled,
        })
        currentConversation.value = updated
      } catch (e) {
        console.error('Failed to update conversation thinking setting:', e)
        ElMessage.error('更新设置失败')
      }
    }
  }

  async function createConversationAndSet(opts: {
    reportIds?: string[]
    datasetIds?: string[]
    title?: string
  } = {}) {
    const conv = await createConversation({
      title: opts.title || '新对话',
      report_ids: opts.reportIds || [],
      dataset_ids: opts.datasetIds || [],
      enable_thinking: enableThinking.value,
    })
    currentConversation.value = conv
    messages.value = []
    enableThinking.value = conv.enable_thinking ?? true

    if (client && isConnected.value) {
      client.send({
        type: 'init',
        conversation_id: currentConversation.value?.id,
      })
      return conv
    }

    await connectWs()
    return conv
  }

  async function updateConversationSettings(
    id: string,
    payload: { title?: string; report_ids?: string[]; dataset_ids?: string[] },
  ) {
    const updated = await updateConversation(id, payload)
    if (currentConversation.value?.id === id) {
      currentConversation.value = updated
    }
    return updated
  }

  function clearMessages() {
    messages.value = []
    streamingMessage.value = ''
    statusMessage.value = ''
    pendingCitations.value = []
  }

  function clearCurrentConversation() {
    currentConversation.value = null
  }

  return {
    currentConversation,
    messages,
    streamingMessage,
    statusMessage,
    isStreaming,
    isConnected,
    enableThinking,
    error,
    initConversation,
    createConversationAndSet,
    updateConversationSettings,
    sendMessage,
    stopGeneration,
    toggleThinking,
    disconnect,
    clearMessages,
    clearCurrentConversation,
  }
})
