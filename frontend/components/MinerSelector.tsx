'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Miner {
  name: string
  display_name: string
}

interface MinerSelectorProps {
  selectedMiner: string
  onSelectMiner: (miner: string) => void
}

export default function MinerSelector({ selectedMiner, onSelectMiner }: MinerSelectorProps) {
  const [miners, setMiners] = useState<Miner[]>([])

  useEffect(() => {
    const fetchMiners = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/miners`)
        setMiners(response.data.miners)
      } catch (error) {
        console.error('Error fetching miners:', error)
      }
    }

    // Fetch miners on mount
    fetchMiners()
    
    // No auto-refresh - miners are discovered when component mounts or page refreshes
  }, [])

  return (
    <div className="mb-6">
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        Select Miner
      </label>
      <div className="flex gap-2">
        {miners.map((miner) => (
          <button
            key={miner.name}
            onClick={() => onSelectMiner(miner.name)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              selectedMiner === miner.name
                ? 'bg-primary-600 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            {miner.display_name}
          </button>
        ))}
      </div>
    </div>
  )
}

