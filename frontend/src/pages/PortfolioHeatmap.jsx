import { useState, useEffect } from 'react'
import { portfolio } from '../api'

const PRESETS = [
  { value: '1d', label: '1 Day' },
  { value: '1w', label: '1 Week' },
  { value: '1m', label: '1 Month' },
  { value: '3m', label: '3 Months' },
  { value: '6m', label: '6 Months' },
  { value: 'ytd', label: 'YTD' },
  { value: '1y', label: '1 Year' },
  { value: '5y', label: '5 Years' },
  { value: 'all', label: 'All Time' },
]

function formatCurrency(value) {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
  }).format(value)
}

function formatPercent(value) {
  return new Intl.NumberFormat('en-CA', {
    style: 'percent',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value / 100)
}

function getHeatmapColor(value) {
  const intensity = Math.min(Math.abs(value) / 30, 1)
  if (value >= 0) {
    return `rgba(34, 197, 94, ${0.3 + intensity * 0.7})`
  }
  return `rgba(239, 68, 68, ${0.3 + intensity * 0.7})`
}

export default function PortfolioHeatmap() {
  const [portfolios, setPortfolios] = useState([])
  const [selectedPortfolio, setSelectedPortfolio] = useState(null)
  const [heatmapData, setHeatmapData] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const [preset, setPreset] = useState('1m')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  useEffect(() => {
    loadPortfolios()
  }, [])

  useEffect(() => {
    if (selectedPortfolio) {
      loadHeatmapData()
    }
  }, [selectedPortfolio, preset, startDate, endDate, useCustom])

  const loadPortfolios = async () => {
    try {
      const response = await portfolio.list()
      const data = Array.isArray(response.data) 
        ? response.data 
        : response.data?.results || []
      setPortfolios(data)
      if (data.length > 0) {
        setSelectedPortfolio(data[0].id)
      }
    } catch (err) {
      setError('Failed to load portfolios')
    } finally {
      setLoading(false)
    }
  }

  const loadHeatmapData = async () => {
    if (!selectedPortfolio) return
    
    setLoading(true)
    setError(null)
    
    try {
      const params = useCustom 
        ? { start_date: startDate, end_date: endDate }
        : { preset }
      
      const [heatmapRes, summaryRes] = await Promise.all([
        portfolio.heatmapDynamic(selectedPortfolio, params),
        portfolio.heatmapSummary(selectedPortfolio, params),
      ])
      
      setHeatmapData(heatmapRes.data)
      setSummary(summaryRes.data)
    } catch (err) {
      setError('Failed to load heatmap data: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePresetChange = (value) => {
    setPreset(value)
    setUseCustom(false)
  }

  const handleCustomChange = () => {
    setUseCustom(true)
    setPreset('')
  }

  if (loading && !heatmapData.length) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Portfolio Heatmap</h1>
        
        <select
          value={selectedPortfolio || ''}
          onChange={(e) => setSelectedPortfolio(Number(e.target.value))}
          className="border rounded px-3 py-2"
        >
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>
              {p.account_type} #{p.id}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-4 mb-6 items-center">
        <div className="flex gap-2 flex-wrap">
          {PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => handlePresetChange(p.value)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                !useCustom && preset === p.value
                  ? 'bg-brand-700 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        
        <div className="flex gap-2 items-center border-l pl-4">
          <label className="text-sm text-gray-600">Custom:</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => { setStartDate(e.target.value); handleCustomChange() }}
            className="border rounded px-2 py-1 text-sm"
          />
          <span className="text-gray-400">to</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => { setEndDate(e.target.value); handleCustomChange() }}
            className="border rounded px-2 py-1 text-sm"
          />
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">
          {error}
        </div>
      )}

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Total Return</div>
            <div className={`text-xl font-semibold ${summary.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(summary.total_return)}
            </div>
            <div className={`text-sm ${summary.total_return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercent(summary.total_return_pct)}
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Best Performer</div>
            <div className="text-xl font-semibold text-green-600">
              {summary.best_symbol}
            </div>
            <div className="text-sm text-green-600">
              {formatPercent(summary.best_return_pct)}
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Worst Performer</div>
            <div className="text-xl font-semibold text-red-600">
              {summary.worst_symbol}
            </div>
            <div className="text-sm text-red-600">
              {formatPercent(summary.worst_return_pct)}
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Average Return</div>
            <div className={`text-xl font-semibold ${summary.average_return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatPercent(summary.average_return_pct)}
            </div>
            <div className="text-sm text-gray-500">
              {summary.stock_count} stocks
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
        <h2 className="text-lg font-semibold p-4 border-b">Holdings Heatmap</h2>
        
        {heatmapData.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No data available for the selected time period. Try loading historical price data first.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">
                    Symbol
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Shares
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Start Price
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    End Price
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Start Value
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    End Value
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Gain/Loss
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Return %
                  </th>
                </tr>
              </thead>
              <tbody>
                {heatmapData
                  .sort((a, b) => b.gain_loss_pct - a.gain_loss_pct)
                  .map((holding, idx) => (
                  <tr 
                    key={holding.symbol} 
                    className="border-t"
                    style={{ backgroundColor: getHeatmapColor(holding.gain_loss_pct) }}
                  >
                    <td className="px-4 py-3 font-medium">
                      {holding.symbol}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {holding.quantity?.toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.start_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.end_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.start_value)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.current_value)}
                    </td>
                    <td className={`px-4 py-3 text-right ${holding.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(holding.gain_loss)}
                    </td>
                    <td className={`px-4 py-3 text-right font-semibold ${holding.gain_loss_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatPercent(holding.gain_loss_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {heatmapData.length > 0 && (
        <div className="mt-4 text-sm text-gray-500">
          <p>Color intensity indicates return magnitude. Green = profit, Red = loss.</p>
          <p>Note: Returns are calculated based on historical price data, not actual transaction history.</p>
        </div>
      )}
    </div>
  )
}
