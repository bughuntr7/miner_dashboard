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
  ComposedChart,
  Area,
  ReferenceArea,
} from 'recharts'
import { formatInTimeZone } from 'date-fns-tz'
import { useAlerts } from '@/components/AlertContainer'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface AssetChartProps {
  minerName: string
  assetName: string
  assetDisplayName: string
  color: string
  limit?: number
  startTime?: string | null
  endTime?: string | null
}

/**
 * Calculate dynamic Y-axis domain based on data range.
 * Includes predictions, intervals, and actual prices with padding.
 */
function calculateYAxisDomain(data: any[]): [number, number] | undefined {
  if (!data || data.length === 0) {
    return undefined
  }

  // Collect all numeric values (predictions, intervals, actuals)
  const values: number[] = []
  
  data.forEach((point) => {
    if (typeof point.prediction === 'number' && !isNaN(point.prediction)) {
      values.push(point.prediction)
    }
    if (typeof point.intervalLower === 'number' && !isNaN(point.intervalLower)) {
      values.push(point.intervalLower)
    }
    if (typeof point.intervalUpper === 'number' && !isNaN(point.intervalUpper)) {
      values.push(point.intervalUpper)
    }
    if (typeof point.actualPrice === 'number' && !isNaN(point.actualPrice)) {
      values.push(point.actualPrice)
    }
  })

  if (values.length === 0) {
    return undefined
  }

  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = maxValue - minValue

  // Handle edge case where all values are the same
  if (range === 0) {
    const center = minValue
    const padding = Math.abs(center) * 0.1 || 1 // 10% of value, or 1 if value is 0
    return [center - padding, center + padding]
  }

  // Add 10% padding on each side
  const padding = range * 0.1
  const domainMin = Math.max(0, minValue - padding) // Don't go below 0 for prices
  const domainMax = maxValue + padding

  return [domainMin, domainMax]
}

export default function AssetChart({ minerName, assetName, assetDisplayName, color, limit = 120, startTime, endTime }: AssetChartProps) {
  const [data, setData] = useState<any[]>([])
  const [metrics, setMetrics] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { showAlert } = useAlerts()

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        setError(null)
        // Build query parameters
        const params = new URLSearchParams({
          limit: limit.toString(),
          fetch_actuals: 'true'
        })
        if (startTime) params.append('start_time', startTime)
        if (endTime) params.append('end_time', endTime)
        
        const response = await axios.get(`${API_URL}/api/miners/${minerName}/asset/${assetName}?${params.toString()}`)
        const chartData = response.data.data || []
        const metricsData = response.data.metrics || null
        setMetrics(metricsData)
        
        // Transform data for chart
        // Use evaluation_time (1 hour after prediction) for x-axis
        const transformedData = chartData.map((point: any) => {
          // Use evaluation_time for x-axis (when actual price is measured)
          const evalTimestamp = point.evaluation_time || point.prediction_time || point.timestamp
          // Parse as UTC - ensure we handle ISO strings correctly
          let evalDate: Date
          if (evalTimestamp) {
            // If it's already an ISO string with timezone, parse it
            // If it's missing timezone, assume UTC
            const ts = evalTimestamp.toString()
            const dateStr = ts.endsWith('Z') || ts.includes('+') || ts.includes('-', 10) 
              ? ts 
              : ts + 'Z'
            evalDate = new Date(dateStr)
          } else {
            evalDate = new Date()
          }
          
          // Also get prediction time for reference
          const predTimestamp = point.prediction_time || point.timestamp
          let predDate: Date | null = null
          if (predTimestamp) {
            const ts = predTimestamp.toString()
            const dateStr = ts.endsWith('Z') || ts.includes('+') || ts.includes('-', 10)
              ? ts
              : ts + 'Z'
            predDate = new Date(dateStr)
          }
          
          const lower = point.interval_lower
          const upper = point.interval_upper
          
          // Format in UTC timezone to ensure correct display
          return {
            time: formatInTimeZone(evalDate, 'UTC', 'HH:mm'),
            timeFull: formatInTimeZone(evalDate, 'UTC', 'HH:mm:ss'),
            date: formatInTimeZone(evalDate, 'UTC', 'MM/dd HH:mm'),
            timestamp: evalDate.getTime(),
            evalDate: evalDate, // Keep full date object for sorting
            prediction: point.prediction,
            intervalLower: lower,
            intervalUpper: upper,
            // For area fill: create a range value
            intervalRange: lower && upper ? (upper - lower) : null,
            actualPrice: point.actual_price,
            hasActual: point.has_actual,
            predictionTime: predDate ? formatInTimeZone(predDate, 'UTC', 'HH:mm') : '',
          }
        })
        
        // Sort by timestamp to ensure correct order
        transformedData.sort((a, b) => a.timestamp - b.timestamp)
        
        setData(transformedData)
        setError(null)
      } catch (error: any) {
        console.error(`Error fetching ${assetName} data:`, error)
        const errorMsg = error.response?.data?.detail || error.message || `Failed to load ${assetDisplayName} data`
        setError(errorMsg)
        // Only show alert for actual API errors, not for missing data
        if (error.response?.status && error.response.status >= 400) {
          showAlert('error', `${assetDisplayName}: ${errorMsg}`, 8000)
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
    
    // No auto-refresh - data is loaded on demand when component mounts or dependencies change
  }, [minerName, assetName, limit, startTime, endTime])

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          {assetDisplayName} Predictions
        </h3>
        <div className="text-center py-8">Loading chart...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          {assetDisplayName} Predictions
        </h3>
        <div className="text-center py-8">
          <div className="text-red-600 dark:text-red-400 mb-2">⚠️ Error loading data</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">{error}</div>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
          {assetDisplayName} Predictions
        </h3>
        <div className="text-center py-8 text-gray-500">No data available</div>
      </div>
    )
  }

  // Check if we have interval data
  const hasIntervals = data.some((d) => d.intervalLower !== null && d.intervalUpper !== null)
  const hasActuals = data.some((d) => d.actualPrice !== null)

  // Calculate dynamic Y-axis domain based on data
  const yAxisDomain = calculateYAxisDomain(data)
  
  // Debug: Log Y-axis domain for troubleshooting
  if (data.length > 0 && yAxisDomain) {
    console.log(`[${assetName}] Y-axis domain:`, yAxisDomain, `Data range:`, {
      min: Math.min(...data.map(d => [d.prediction, d.intervalLower, d.intervalUpper, d.actualPrice].filter(v => typeof v === 'number')).flat()),
      max: Math.max(...data.map(d => [d.prediction, d.intervalLower, d.intervalUpper, d.actualPrice].filter(v => typeof v === 'number')).flat())
    })
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 relative">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
        {assetDisplayName} Predictions vs Actual Prices
      </h3>
      
      {/* Metrics Box (top-left corner, like matplotlib) */}
      {metrics && (
        <div className="absolute top-16 left-4 z-10 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded-lg p-3 text-xs font-mono shadow-lg">
          <div className="space-y-0.5 text-gray-800 dark:text-gray-200">
            <div>MAPE: {metrics.mape?.toFixed(2) || 'N/A'}%</div>
            <div>MAE: ${metrics.mae?.toFixed(2) || 'N/A'}</div>
            <div>RMSE: ${metrics.rmse?.toFixed(2) || 'N/A'}</div>
            <div>Bias: {metrics.bias_pct?.toFixed(2) || 'N/A'}%</div>
            {metrics.coverage !== undefined && (
              <>
                <div>Coverage: {metrics.coverage.toFixed(1)}%</div>
                <div>Interval Width: {metrics.avg_interval_width_pct?.toFixed(1) || 'N/A'}%</div>
              </>
            )}
          </div>
        </div>
      )}
      
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={data}>
          <defs>
            <linearGradient id={`gradient${assetName}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis 
            dataKey="timestamp" 
            type="number"
            domain={['dataMin', 'dataMax']}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickFormatter={(value) => {
              return formatInTimeZone(new Date(value), 'UTC', 'HH:mm')
            }}
            label={{ value: 'Evaluation Time (UTC)', position: 'insideBottom', offset: -5, style: { fill: '#6b7280' } }}
            angle={-45}
            textAnchor="end"
            height={60}
            allowDecimals={false}
          />
          <YAxis 
            type="number"
            domain={yAxisDomain || ['dataMin', 'dataMax']}
            tick={{ fill: '#6b7280', fontSize: 12 }}
            tickFormatter={(value) => {
              return `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
            }}
            label={{ value: 'Price (USD)', angle: -90, position: 'insideLeft', style: { fill: '#6b7280' } }}
            allowDecimals={true}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: '#1f2937', 
              border: '1px solid #374151',
              borderRadius: '8px',
            }}
            labelStyle={{ color: '#fff', fontWeight: 'bold' }}
            formatter={(value: any, name: string) => {
              if (typeof value === 'number') {
                return [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, name]
              }
              return [value, name]
            }}
            labelFormatter={(label) => {
              // label is the timestamp value
              const point = data.find(d => d.timestamp === label)
              if (point) {
                return `Time: ${formatInTimeZone(point.evalDate, 'UTC', 'MM/dd HH:mm:ss')} UTC`
              }
              return `Time: ${formatInTimeZone(new Date(label), 'UTC', 'MM/dd HH:mm:ss')} UTC`
            }}
          />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
          
          {/* Prediction Interval (Shaded Area between lower and upper) */}
          {/* Use Area component with base referencing the lower bound */}
          {hasIntervals && (
            <Area
              type="monotone"
              dataKey="intervalUpper"
              base="intervalLower"
              stroke="none"
              fill={color}
              fillOpacity={0.2}
              name="Prediction Interval"
              connectNulls
              isAnimationActive={false}
            />
          )}
          
          {/* Interval Lower Bound (dashed line) */}
          {hasIntervals && (
            <Line 
              type="monotone" 
              dataKey="intervalLower" 
              stroke={color} 
              strokeWidth={1.5}
              strokeDasharray="5 5"
              name="Interval Lower"
              dot={false}
              strokeOpacity={0.7}
              connectNulls
              isAnimationActive={false}
            />
          )}
          
          {/* Interval Upper Bound (dashed line) */}
          {hasIntervals && (
            <Line 
              type="monotone" 
              dataKey="intervalUpper" 
              stroke={color} 
              strokeWidth={1.5}
              strokeDasharray="5 5"
              name="Interval Upper"
              dot={false}
              strokeOpacity={0.7}
              connectNulls
              isAnimationActive={false}
            />
          )}
          
          {/* Prediction Line (main line) - Draw on top of interval */}
          <Line 
            type="monotone" 
            dataKey="prediction" 
            stroke={color} 
            strokeWidth={3}
            name="Prediction"
            dot={false}
            activeDot={{ r: 5, fill: color }}
            connectNulls
            isAnimationActive={false}
          />
          
          {/* Actual Price (green line when available) - Draw on top */}
          {hasActuals && (
            <Line 
              type="monotone" 
              dataKey="actualPrice" 
              stroke="#10b981" 
              strokeWidth={3}
              name="Actual Price"
              dot={{ r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff' }}
              activeDot={{ r: 6, fill: '#10b981' }}
              connectNulls
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      
      {/* Stats */}
      <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-gray-500 dark:text-gray-400">Data Points:</span>
          <span className="ml-2 font-medium text-gray-900 dark:text-white">{data.length}</span>
        </div>
        {hasIntervals && (
          <div>
            <span className="text-gray-500 dark:text-gray-400">With Intervals:</span>
            <span className="ml-2 font-medium text-gray-900 dark:text-white">
              {data.filter((d) => d.intervalLower !== null && d.intervalUpper !== null).length}
            </span>
          </div>
        )}
        {hasActuals && (
          <div>
            <span className="text-gray-500 dark:text-gray-400">With Actuals:</span>
            <span className="ml-2 font-medium text-green-600 dark:text-green-400">
              {data.filter((d) => d.actualPrice !== null).length}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

