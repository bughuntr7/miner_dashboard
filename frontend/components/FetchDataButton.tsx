'use client'

import { useState } from 'react'
import axios from 'axios'
import { useAlerts } from '@/components/AlertContainer'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface FetchDataButtonProps {
  onFetchComplete?: () => void
}

export default function FetchDataButton({ onFetchComplete }: FetchDataButtonProps) {
  const [isFetching, setIsFetching] = useState(false)
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null)
  const [fetchStatus, setFetchStatus] = useState<string>('')
  const { showAlert } = useAlerts()

  const handleFetch = async () => {
    setIsFetching(true)
    setFetchStatus('Fetching actual prices from APIs...')
    
    try {
      const url = `${API_URL}/api/fetch-data`
      console.log('Fetching from:', url)
      const response = await axios.post(url, {
        fetch_prices: true
      }, {
        headers: {
          'Content-Type': 'application/json'
        }
      })
      
      if (response.data.success) {
        const results = response.data.results
        const miners = Object.keys(results)
        const successCount = miners.filter(m => results[m].success).length
        const priceCounts = miners
          .map(m => results[m].prices_fetched || 0)
          .reduce((a, b) => a + b, 0)
        const skippedCounts = miners
          .map(m => results[m].prices_skipped || 0)
          .reduce((a, b) => a + b, 0)
        
        // Build detailed message with time range info
        let successMsg = `Fetched ${priceCounts} new prices`
        if (skippedCounts > 0) {
          successMsg += `, ${skippedCounts} already in database`
        }
        successMsg += ` for ${successCount}/${miners.length} miners.`
        
        // Add time range info if available
        const firstMiner = miners.find(m => results[m].success && results[m].time_range)
        if (firstMiner && results[firstMiner].time_range) {
          const tr = results[firstMiner].time_range
          if (tr.earliest_evaluation && tr.latest_evaluation) {
            const earliest = new Date(tr.earliest_evaluation).toLocaleDateString()
            const latest = new Date(tr.latest_evaluation).toLocaleDateString()
            successMsg += ` Time range: ${earliest} to ${latest}`
          }
        }
        
        setFetchStatus(`✅ ${successMsg}`)
        setLastFetchTime(new Date())
        showAlert('success', successMsg, 8000)
        
        // Trigger refresh
        if (onFetchComplete) {
          setTimeout(() => {
            onFetchComplete()
            setFetchStatus('')
          }, 2000)
        }
      } else {
        const failMsg = 'Fetch failed. Check backend logs.'
        setFetchStatus(`❌ ${failMsg}`)
        showAlert('error', failMsg, 8000)
      }
    } catch (error: any) {
      console.error('Fetch error:', error)
      console.error('Error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        url: error.config?.url
      })
      const errorMsg = error.response?.data?.detail || error.response?.statusText || error.message || 'Unknown error'
      const fullErrorMsg = `Error: ${errorMsg} (Status: ${error.response?.status || 'N/A'})`
      setFetchStatus(`❌ ${fullErrorMsg}`)
      showAlert('error', `Data fetch failed: ${errorMsg}`, 10000)
    } finally {
      setIsFetching(false)
    }
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={handleFetch}
        disabled={isFetching}
        className={`
          px-6 py-2 rounded-lg font-medium transition-all
          ${isFetching
            ? 'bg-gray-400 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }
          text-white shadow-md hover:shadow-lg
          disabled:opacity-50
          flex items-center gap-2
        `}
      >
        {isFetching ? (
          <>
            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Fetching...
          </>
        ) : (
          <>
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Fetch Data
          </>
        )}
      </button>
      
      {fetchStatus && (
        <div className={`
          text-sm px-3 py-1 rounded
          ${fetchStatus.startsWith('✅') 
            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' 
            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
          }
        `}>
          {fetchStatus}
        </div>
      )}
      
      {lastFetchTime && !fetchStatus && (
        <div className="text-xs text-gray-500 dark:text-gray-400">
          Last fetched: {lastFetchTime.toLocaleTimeString()}
        </div>
      )}
    </div>
  )
}

