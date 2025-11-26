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
import { formatInTimeZone } from 'date-fns-tz'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface TrustChartProps {
  minerName: string
  limit?: number
}

export default function TrustChart({ minerName, limit = 50 }: TrustChartProps) {
  const [data, setData] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchTrust = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/miners/${minerName}/trust?limit=${limit}`)
        const trustData = response.data.trust || []
        
        // Transform data for chart
        // Backend already returns data in oldest-to-newest order, so no need to reverse
        const chartData = trustData.map((item: any) => {
            const timestamp = item.timestamp || item.datetime
            const date = timestamp ? new Date(timestamp) : new Date()
            
            // Format in UTC timezone to ensure correct display (timestamps are in UTC)
            return {
              time: formatInTimeZone(date, 'UTC', 'HH:mm'),
              timestamp: date.getTime(),
              trust: item.trust
            }
          })
        
        // Sort by timestamp to ensure correct order (oldest to newest)
        chartData.sort((a, b) => a.timestamp - b.timestamp)
        
        setData(chartData)
      } catch (error: any) {
        console.error('Error fetching trust:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchTrust()
  }, [minerName, limit])

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
        <h3 className="text-lg font-semibold mb-4">Trust History</h3>
        <div className="text-center py-8 text-gray-500">No data available</div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
        Trust History (Last {limit})
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
            label={{ value: 'Trust', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#fff' }}
          />
          <Legend />
          <Line 
            type="monotone" 
            dataKey="trust" 
            stroke="#10b981" 
            strokeWidth={2}
            name="Trust"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

