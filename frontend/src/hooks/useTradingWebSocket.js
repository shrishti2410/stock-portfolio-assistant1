/**
 * WebSocket hook for real-time trading updates.
 * Connects to /ws/trading and dispatches events.
 */
import { useState, useEffect, useRef, useCallback } from 'react'

const WS_URL = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/trading'

export default function useTradingWebSocket() {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [proposals, setProposals] = useState([])
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        console.log('[WS] Connected to trading engine')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastMessage(data)

          if (data.type === 'new_proposal') {
            setProposals(prev => [data.proposal, ...prev])
          } else if (data.type === 'position_opened' || data.type === 'position_closed') {
            // Trigger refresh in consuming components
          }
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Auto-reconnect after 5 seconds
        reconnectRef.current = setTimeout(connect, 5000)
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch (e) {
      console.error('[WS] Connection error:', e)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
    }
  }, [connect])

  const clearProposal = useCallback((id) => {
    setProposals(prev => prev.filter(p => p.id !== id))
  }, [])

  return { connected, lastMessage, proposals, clearProposal }
}
