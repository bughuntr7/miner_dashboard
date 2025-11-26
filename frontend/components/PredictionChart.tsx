'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { format } from 'date-fns'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface PredictionChartProps {
  minerName: string
}

export default function PredictionChart({ minerName }: PredictionChartProps) {
  const [data, setData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/miners/${minerName}/predictions?limit=50`)
        const predictions = response.data.predictions || []
        
        // Transform data for chart and deduplicate by timestamp
        // Group by timestamp to handle cases where multiple predictions exist at the same timestamp
        const timestampMap = new Map<string, any>()
        
        predictions.forEach((pred: any) => {
          const timestamp = pred.timestamp || pred.datetime
          const date = timestamp ? new Date(timestamp) : new Date()
          const timestampKey = date.getTime().toString() // Use milliseconds as unique key
          
          // Only keep the first prediction for each unique timestamp
          if (!timestampMap.has(timestampKey)) {
            const chartPoint: any = {
              time: format(date, 'HH:mm'),
              timestamp: date.getTime(),
            }
            
            // Add predictions for each asset
            if (pred.btc_prediction) chartPoint.btc = pred.btc_prediction
            if (pred.eth_prediction) chartPoint.eth = pred.eth_prediction
            if (pred.tao_bittensor_prediction) chartPoint.tao = pred.tao_bittensor_prediction
            
            timestampMap.set(timestampKey, chartPoint)
          }
        })
        
        // Convert map to array and sort by timestamp (oldest to newest for chart display)
        const chartData = Array.from(timestampMap.values())
          .sort((a, b) => a.timestamp - b.timestamp) // Sort ascending: oldest to newest
        
        setData(chartData)
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
        <div className="text-center py-8">Loading chart...</div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Prediction Trends</h3>
        <div className="text-center py-8 text-gray-500">No data available</div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
        Prediction Trends (Last 50)
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="time" 
            tick={{ fill: '#6b7280' }}
            label={{ value: 'Time', position: 'insideBottom', offset: -5 }}
          />
          <YAxis 
            tick={{ fill: '#6b7280' }}
            label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#fff' }}
          />
          <Legend />
          {data.some((d) => d.btc !== undefined) && (
            <Line 
              type="monotone" 
              dataKey="btc" 
              stroke="#f59e0b" 
              strokeWidth={2}
              name="BTC"
              dot={false}
            />
          )}
          {data.some((d) => d.eth !== undefined) && (
            <Line 
              type="monotone" 
              dataKey="eth" 
              stroke="#3b82f6" 
              strokeWidth={2}
              name="ETH"
              dot={false}
            />
          )}
          {data.some((d) => d.tao !== undefined) && (
            <Line 
              type="monotone" 
              dataKey="tao" 
              stroke="#10b981" 
              strokeWidth={2}
              name="TAO"
              dot={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

