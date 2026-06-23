import { getToken } from './client'
import type { WsClientMessage, WsServerMessage } from '@/types'

type ServerMessageHandler = (msg: WsServerMessage) => void
type CloseHandler = (event: CloseEvent) => void
type StatusHandler = (status: 'connecting' | 'open' | 'closed') => void

const RECONNECT_DELAYS = [1000, 2000, 5000, 10000, 30000]

export class WsChatClient {
  private ws: WebSocket | null = null
  private readonly token: string
  private serverHandlers: ServerMessageHandler[] = []
  private closeHandlers: CloseHandler[] = []
  private statusHandlers: StatusHandler[] = []
  private reconnectAttempt = 0
  private manualClose = false
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  constructor(token?: string) {
    this.token = token || getToken() || ''
  }

  connect(): Promise<void> {
    this.manualClose = false
    return new Promise((resolve, reject) => {
      const baseURL = import.meta.env.VITE_API_BASE || '/api'
      const wsBase = baseURL.replace(/^http/, 'ws')
      const url = `${wsBase}/ws/chat?token=${encodeURIComponent(this.token)}`
      this.emitStatus('connecting')
      this.ws = new WebSocket(url)
      const onFirstError = (e: Event) => {
        reject(e)
      }
      this.ws.addEventListener('error', onFirstError, { once: true })
      this.ws.onopen = () => {
        this.reconnectAttempt = 0
        this.emitStatus('open')
        resolve()
      }
      this.ws.onmessage = (event) => this.handleMessage(event)
      this.ws.onclose = (event) => {
        this.emitStatus('closed')
        this.closeHandlers.forEach((cb) => cb(event))
        if (!this.manualClose) {
          this.scheduleReconnect()
        }
      }
      this.ws.onerror = () => {
        // silent — onclose will follow and may trigger reconnect
      }
    })
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectAttempt, RECONNECT_DELAYS.length - 1)]
    this.reconnectAttempt += 1
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect().catch(() => { /* next onclose will retry */ })
    }, delay)
  }

  private handleMessage(event: MessageEvent) {
    let parsed: WsServerMessage
    try {
      parsed = JSON.parse(event.data) as WsServerMessage
    } catch {
      return
    }
    this.serverHandlers.forEach((cb) => cb(parsed))
  }

  send(msg: WsClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }
    this.ws.send(JSON.stringify(msg))
  }

  onMessage(cb: ServerMessageHandler): void {
    this.serverHandlers.push(cb)
  }

  onClose(cb: CloseHandler): void {
    this.closeHandlers.push(cb)
  }

  onStatus(cb: StatusHandler): void {
    this.statusHandlers.push(cb)
  }

  close(): void {
    this.manualClose = true
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.serverHandlers = []
    this.closeHandlers = []
    this.statusHandlers = []
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  private emitStatus(status: 'connecting' | 'open' | 'closed') {
    this.statusHandlers.forEach((cb) => cb(status))
  }

  get isConnected(): boolean {
    return !!this.ws && this.ws.readyState === WebSocket.OPEN
  }
}
