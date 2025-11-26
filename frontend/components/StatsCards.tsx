'use client'

interface StatsCardsProps {
  stats: any
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const assets = stats.assets ? Object.keys(stats.assets) : []

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* Total Predictions */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Total Predictions
        </div>
        <div className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
          {stats.total_predictions || 0}
        </div>
      </div>

      {/* Recent Predictions */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Recent (24h)
        </div>
        <div className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
          {stats.recent_predictions || 0}
        </div>
      </div>

      {/* Pending Evaluations */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Pending Evaluations
        </div>
        <div className="mt-2 text-3xl font-bold text-yellow-600 dark:text-yellow-400">
          {stats.pending_evaluations || 0}
        </div>
      </div>

      {/* Validators */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Validators
        </div>
        <div className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
          {stats.validator_stats?.total_validators || 0}
        </div>
      </div>

      {/* Asset-specific stats */}
      {assets.map((asset) => {
        const assetStats = stats.assets[asset]
        const basicStats = assetStats?.basic_stats || {}
        const trends = assetStats?.trends || {}

        return (
          <div key={asset} className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <div className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
              {asset.toUpperCase()}
            </div>
            {basicStats.latest_prediction && (
              <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">
                ${basicStats.latest_prediction.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
            )}
            {trends.trend_percentage !== undefined && (
              <div className={`text-sm ${trends.trend_percentage >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {trends.trend_percentage >= 0 ? '↑' : '↓'} {Math.abs(trends.trend_percentage).toFixed(2)}%
              </div>
            )}
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Avg Processing: {basicStats.avg_processing_time?.toFixed(3) || 'N/A'}s
            </div>
          </div>
        )
      })}
    </div>
  )
}

