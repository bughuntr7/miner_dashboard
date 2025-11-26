'use client'

import { useState, useEffect, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<number | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    // Get WebSocket URL from API URL
    const getWebSocketUrl = () => {
      try {
        const url = new URL(API_URL)
        return `ws://${url.hostname}:${url.port || '8000'}`
      } catch {
        // Fallback if URL parsing fails
        return 'ws://localhost:8000'
      }
    }

    const connect = () => {
      try {
        const wsUrl = `${getWebSocketUrl()}/ws`
        console.log('Connecting to WebSocket:', wsUrl)
        const ws = new WebSocket(wsUrl)
        
        ws.onopen = () => {
          console.log('WebSocket connected')
          setIsConnected(true)
          setConnectionError(null)
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
          }
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'update') {
              setLastUpdate(Date.now())
            }
          } catch (e) {
            console.error('Error parsing WebSocket message:', e)
          }
        }

        ws.onerror = (error) => {
          console.warn('WebSocket error (non-critical - dashboard works without it):', error)
          console.warn('WebSocket readyState:', ws.readyState)
          console.warn('WebSocket URL:', wsUrl)
          // Don't set error here - let onclose handle it
          // WebSocket is optional - dashboard works fine without it
        }

        ws.onclose = (event) => {
          console.log('WebSocket disconnected (non-critical)', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
            readyState: ws.readyState
          })
          setIsConnected(false)
          
          // Set error message based on close code (but it's not critical)
          if (event.code !== 1000 && event.code !== 1001) {
            const errorMsg = event.reason || `Real-time updates unavailable (code: ${event.code})`
            setConnectionError(errorMsg)
          } else {
            setConnectionError(null)
          }
          
          // Only reconnect if it wasn't a clean close or unexpected close
          if (event.code !== 1000 && event.code !== 1001) {
            // Reconnect after 5 seconds (longer delay since it's not critical)
            reconnectTimeoutRef.current = setTimeout(() => {
              console.log('Attempting to reconnect WebSocket (optional real-time updates)...')
              connect()
            }, 5000)
          }
        }

        wsRef.current = ws
      } catch (error: any) {
        console.warn('Error connecting WebSocket (non-critical):', error)
        setIsConnected(false)
        setConnectionError(error.message || 'Real-time updates unavailable')
        
        // Retry connection after longer delay (not critical)
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 5000)
      }
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  return { isConnected, lastUpdate, connectionError }
}

