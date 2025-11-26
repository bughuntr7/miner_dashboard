'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import { format } from 'date-fns'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface LatestPredictionsProps {
  minerName: string
}

export default function LatestPredictions({ minerName }: LatestPredictionsProps) {
  const [predictions, setPredictions] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/miners/${minerName}/predictions?limit=10`)
        setPredictions(response.data.predictions || [])
      } catch (error: any) {
        console.error('Error fetching predictions:', error)
        // Don't show error alert here - component will show empty state
        // Errors are handled at component level
      } finally {
        setIsLoading(false)
      }
    }

    fetchPredictions()
    
    // No auto-refresh - predictions are loaded on demand when miner changes
  }, [minerName])

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-center py-8">Loading...</div>
      </div>
    )
  }

  if (predictions.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          Latest Predictions
        </h3>
        <div className="text-center py-8 text-gray-500">No predictions available</div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
        Latest Predictions
      </h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {predictions.map((pred, idx) => {
          const timestamp = pred.timestamp || pred.datetime
          const date = timestamp ? new Date(timestamp) : new Date()
          
          return (
            <div
              key={idx}
              className="border-b border-gray-200 dark:border-gray-700 pb-3 last:border-0"
            >
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                {format(date, 'MMM dd, HH:mm:ss')}
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                {pred.btc_prediction && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">BTC:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-white">
                      ${pred.btc_prediction.toLocaleString(undefined, {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      })}
                    </span>
                  </div>
                )}
                {pred.eth_prediction && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">ETH:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-white">
                      ${pred.eth_prediction.toLocaleString(undefined, {
                        minimumFractionDigits: 0,
                        maximumFractionDigits: 0,
                      })}
                    </span>
                  </div>
                )}
                {pred.tao_bittensor_prediction && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">TAO:</span>
                    <span className="ml-2 font-medium text-gray-900 dark:text-white">
                      ${pred.tao_bittensor_prediction.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                )}
              </div>
              {pred.processing_time_seconds && (
                <div className="text-xs text-gray-400 mt-1">
                  Processing: {pred.processing_time_seconds.toFixed(3)}s
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

