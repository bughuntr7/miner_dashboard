'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function useMinerStats(minerName: string) {
  const [data, setData] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true)
        const response = await axios.get(`${API_URL}/api/miners/${minerName}/stats`)
        setData(response.data)
        setError(null)
      } catch (err: any) {
        const errorMsg = err.response?.data?.detail || err.message || 'Failed to load miner stats'
        setError(errorMsg)
        setData(null)
      } finally {
        setIsLoading(false)
      }
    }

    fetchStats()
    
    // No auto-refresh - stats are loaded on demand when miner changes
  }, [minerName])

  return { data, isLoading, error }
}

