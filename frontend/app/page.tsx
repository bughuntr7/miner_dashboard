'use client'

import { useState, useEffect } from 'react'
import MinerSelector from '@/components/MinerSelector'
import AssetChart from '@/components/AssetChart'
import IncentiveChart from '@/components/IncentiveChart'
import TrustChart from '@/components/TrustChart'
import { useMinerStats } from '@/hooks/useMinerStats'

export default function Home() {
  const [selectedMiner, setSelectedMiner] = useState<string>('miner1')
  const [dataLimit, setDataLimit] = useState<number>(120)
  const [incentiveLimit, setIncentiveLimit] = useState<number>(50)
  const [trustLimit, setTrustLimit] = useState<number>(50)
  const [startTime, setStartTime] = useState<string | null>(null)
  const [endTime, setEndTime] = useState<string | null>(null)
  const [startDateInput, setStartDateInput] = useState<string>('')
  const [startTimeInput, setStartTimeInput] = useState<string>('')
  const [endDateInput, setEndDateInput] = useState<string>('')
  const [endTimeInput, setEndTimeInput] = useState<string>('')
  const [refreshKey, setRefreshKey] = useState(0)
  const { isLoading } = useMinerStats(selectedMiner)
  
  const limitOptions = [48, 72, 96, 120, 144, 168, 192, 216, 240, 480, 720]
  const incentiveLimitOptions = [25, 50, 100, 200, 300, 500]
  const trustLimitOptions = [25, 50, 100, 200, 300, 500]
  
  // Helper functions for separate date and time inputs (UTC)
  const formatDate = (isoString: string | null): string => {
    if (!isoString) return ''
    const date = new Date(isoString)
    const year = date.getUTCFullYear()
    const month = String(date.getUTCMonth() + 1).padStart(2, '0')
    const day = String(date.getUTCDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  
  const formatTime = (isoString: string | null): string => {
    if (!isoString) return ''
    const date = new Date(isoString)
    const hours = String(date.getUTCHours()).padStart(2, '0')
    const minutes = String(date.getUTCMinutes()).padStart(2, '0')
    return `${hours}:${minutes}`
  }
  
  // Combine date and time into UTC ISO string
  const combineDateTime = (dateStr: string, timeStr: string): string | null => {
    if (!dateStr || !timeStr) return null
    const [year, month, day] = dateStr.split('-').map(Number)
    const [hours, minutes] = timeStr.split(':').map(Number)
    const date = new Date(Date.UTC(year, month - 1, day, hours, minutes, 0, 0))
    return date.toISOString()
  }
  
  // Update combined startTime when date or time changes
  const handleStartDateChange = (date: string) => {
    setStartDateInput(date)
    if (date && startTimeInput) {
      const combined = combineDateTime(date, startTimeInput)
      setStartTime(combined)
      if (combined) setDataLimit(720)
    } else {
      setStartTime(null)
    }
  }
  
  const handleStartTimeChange = (time: string) => {
    setStartTimeInput(time)
    if (startDateInput && time) {
      const combined = combineDateTime(startDateInput, time)
      setStartTime(combined)
      if (combined) setDataLimit(720)
    } else {
      setStartTime(null)
    }
  }
  
  // Update combined endTime when date or time changes
  const handleEndDateChange = (date: string) => {
    setEndDateInput(date)
    if (date && endTimeInput) {
      const combined = combineDateTime(date, endTimeInput)
      setEndTime(combined)
      if (combined) setDataLimit(720)
    } else {
      setEndTime(null)
    }
  }
  
  const handleEndTimeChange = (time: string) => {
    setEndTimeInput(time)
    if (endDateInput && time) {
      const combined = combineDateTime(endDateInput, time)
      setEndTime(combined)
      if (combined) setDataLimit(720)
    } else {
      setEndTime(null)
    }
  }
  
  // Initialize inputs from existing startTime/endTime
  useEffect(() => {
    if (startTime && !startDateInput) {
      setStartDateInput(formatDate(startTime))
      setStartTimeInput(formatTime(startTime))
    }
    if (endTime && !endDateInput) {
      setEndDateInput(formatDate(endTime))
      setEndTimeInput(formatTime(endTime))
    }
  }, [startTime, endTime])
  
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
            Miner Dashboard
          </h1>
        </div>

        {/* Miner Selector */}
        <MinerSelector
          selectedMiner={selectedMiner}
          onSelectMiner={setSelectedMiner}
        />

        {/* Asset Charts */}
        {isLoading ? (
          <div className="text-center py-8">Loading charts...</div>
        ) : (
          <div className="mt-6">
            <div className="mb-4">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Asset Performance Analysis
                </h2>
                <div className="flex items-center gap-2">
                  <label htmlFor="data-limit" className="text-sm text-gray-600 dark:text-gray-400">
                    Data Points:
                  </label>
                  <select
                    id="data-limit"
                    value={dataLimit}
                    onChange={(e) => {
                      setDataLimit(Number(e.target.value))
                      // Clear time range when using data points
                      setStartTime(null)
                      setEndTime(null)
                      setStartDateInput('')
                      setStartTimeInput('')
                      setEndDateInput('')
                      setEndTimeInput('')
                    }}
                    className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {limitOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              
              {/* Time Range Selector */}
              <div className="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <div className="flex items-center gap-6 flex-wrap">
                  {/* Start Time */}
                  <div className="flex items-center gap-3">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      Start (UTC):
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="date"
                        value={startDateInput ? startDateInput : (startTime ? formatDate(startTime) : '')}
                        onChange={(e) => handleStartDateChange(e.target.value)}
                        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <input
                        type="time"
                        value={startTimeInput ? startTimeInput : (startTime ? formatTime(startTime) : '')}
                        onChange={(e) => handleStartTimeChange(e.target.value)}
                        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                  
                  {/* End Time */}
                  <div className="flex items-center gap-3">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                      End (UTC):
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="date"
                        value={endDateInput ? endDateInput : (endTime ? formatDate(endTime) : '')}
                        onChange={(e) => handleEndDateChange(e.target.value)}
                        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <input
                        type="time"
                        value={endTimeInput ? endTimeInput : (endTime ? formatTime(endTime) : '')}
                        onChange={(e) => handleEndTimeChange(e.target.value)}
                        className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                  
                  {(startTime || endTime) && (
                    <button
                      onClick={() => {
                        setStartTime(null)
                        setEndTime(null)
                        setStartDateInput('')
                        setStartTimeInput('')
                        setEndDateInput('')
                        setEndTimeInput('')
                      }}
                      className="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
                    >
                      Clear Range
                    </button>
                  )}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-6">
              <AssetChart 
                key={`${selectedMiner}-btc-${refreshKey}-${dataLimit}-${startTime}-${endTime}`}
                minerName={selectedMiner}
                assetName="btc"
                assetDisplayName="Bitcoin (BTC)"
                color="#f59e0b"
                limit={dataLimit}
                startTime={startTime}
                endTime={endTime}
              />
              <AssetChart 
                key={`${selectedMiner}-eth-${refreshKey}-${dataLimit}-${startTime}-${endTime}`}
                minerName={selectedMiner}
                assetName="eth"
                assetDisplayName="Ethereum (ETH)"
                color="#3b82f6"
                limit={dataLimit}
                startTime={startTime}
                endTime={endTime}
              />
              <AssetChart 
                key={`${selectedMiner}-tao-${refreshKey}-${dataLimit}-${startTime}-${endTime}`}
                minerName={selectedMiner}
                assetName="tao"
                assetDisplayName="Bittensor (TAO)"
                color="#10b981"
                limit={dataLimit}
                startTime={startTime}
                endTime={endTime}
              />
            </div>
          </div>
        )}

        {/* Incentive Chart */}
        <div className="mt-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Incentive History
            </h2>
            <div className="flex items-center gap-2">
              <label htmlFor="incentive-limit" className="text-sm text-gray-600 dark:text-gray-400">
                Data Points:
              </label>
              <select
                id="incentive-limit"
                value={incentiveLimit}
                onChange={(e) => setIncentiveLimit(Number(e.target.value))}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {incentiveLimitOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <IncentiveChart 
            key={`${selectedMiner}-incentive-${refreshKey}-${incentiveLimit}`}
            minerName={selectedMiner} 
            limit={incentiveLimit}
          />
        </div>

        {/* Trust Chart */}
        <div className="mt-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Trust History
            </h2>
            <div className="flex items-center gap-2">
              <label htmlFor="trust-limit" className="text-sm text-gray-600 dark:text-gray-400">
                Data Points:
              </label>
              <select
                id="trust-limit"
                value={trustLimit}
                onChange={(e) => setTrustLimit(Number(e.target.value))}
                className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {trustLimitOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <TrustChart 
            key={`${selectedMiner}-trust-${refreshKey}-${trustLimit}`}
            minerName={selectedMiner} 
            limit={trustLimit}
          />
        </div>
      </div>
    </main>
  )
}

