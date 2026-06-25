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
  const currentAssistantId = ref<string | null>(null)
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
    if (currentConversation.value?.id) {
      client.send({
        type: 'init',
        conversation_id: currentConversation.value.id,
      })
    }
  }

  async function initConversation(opts: {
    assistantId: string
    conversationId?: string
  }) {
    error.value = null
    currentAssistantId.value = opts.assistantId

    if (opts.conversationId) {
      const conv = await getConversation(opts.conversationId)
      currentConversation.value = conv
      messages.value = conv.messages
      enableThinking.value = conv.enable_thinking ?? true
    } else {
      currentConversation.value = null
      messages.value = []
    }

    if (client && isConnected.value && currentConversation.value?.id) {
      client.send({
        type: 'init',
        conversation_id: currentConversation.value.id,
      })
      return
    }

    if (currentConversation.value?.id) {
      await connectWs()
    } else {
      if (client) {
        client.close()
        client = null
      }
      isConnected.value = false
    }
  }

  function handleServerMessage(msg: WsServerMessage) {
    switch (msg.type) {
      case 'connected':
        if (currentConversation.value) {
          currentConversation.value.id = msg.session_id
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
          citations: msg.citations?.length ? msg.citations : [...pendingCitations.value],
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

  async function createConversationAndConnect(assistantId: string, title = '新对话') {
    const conv = await createConversation({
      assistant_id: assistantId,
      title,
      enable_thinking: enableThinking.value,
    })
    currentAssistantId.value = assistantId
    currentConversation.value = conv
    messages.value = []
    enableThinking.value = conv.enable_thinking ?? true
    await connectWs()
    return conv
  }

  async function sendMessage(content: string) {
    if (!currentAssistantId.value) {
      ElMessage.warning('请先选择助手')
      return
    }
    if (!currentConversation.value) {
      await createConversationAndConnect(currentAssistantId.value)
    }
    if (!client || !isConnected.value) {
      ElMessage.warning('会话未连接，正在重连...')
      await connectWs()
    }
    if (!content.trim() || isStreaming.value) return

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
      const autoTitle = content.slice(0, 30) + (content.length > 30 ? '...' : '')
      try {
        const updated = await updateConversation(currentConversation.value.id, {
          title: autoTitle,
        })
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

  function clearCurrentConversation() {
    currentConversation.value = null
    messages.value = []
  }

  return {
    currentConversation,
    currentAssistantId,
    messages,
    streamingMessage,
    statusMessage,
    isStreaming,
    isConnected,
    enableThinking,
    error,
    initConversation,
    createConversationAndConnect,
    sendMessage,
    stopGeneration,
    disconnect,
    clearCurrentConversation,
  }
})
