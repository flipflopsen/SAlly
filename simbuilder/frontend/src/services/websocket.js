/**
 * WebSocket service for real-time collaborative editing
 */
export class WebSocketService {
  constructor(projectId) {
    this.projectId = projectId
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.handlers = {}
  }

  connect(handlers = {}) {
    this.handlers = handlers

    // Determine WebSocket URL based on current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/graph/${this.projectId}/`

    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.attemptReconnect()
    }
  }

  handleMessage(message) {
    const { type, data } = message

    switch (type) {
      case 'node_update':
        this.handlers.onNodeUpdate?.(data)
        break
      case 'node_create':
        this.handlers.onNodeCreate?.(data)
        break
      case 'node_delete':
        this.handlers.onNodeDelete?.(data)
        break
      case 'connection_create':
        this.handlers.onConnectionCreate?.(data)
        break
      case 'connection_delete':
        this.handlers.onConnectionDelete?.(data)
        break
      default:
        console.warn('Unknown message type:', type)
    }
  }

  send(message) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket not connected, message not sent')
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * this.reconnectAttempts

      console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

      setTimeout(() => {
        this.connect(this.handlers)
      }, delay)
    } else {
      console.error('Max reconnection attempts reached')
    }
  }
}
