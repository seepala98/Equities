import { useState, useEffect } from 'react'
import { portfolio } from '../api'
import { Line, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
)

export default function Portfolio() {
  console.log('Portfolio component mounted')
  const [portfolios, setPortfolios] = useState([])
  const [selectedPortfolio, setSelectedPortfolio] = useState(null)
  const [holdings, setHoldings] = useState([])
  const [performance, setPerformance] = useState(null)
  const [heatmapData, setHeatmapData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [debug, setDebug] = useState([])

  const log = (...args) => {
    setDebug(prev => [...prev, args.join(' ')])
    console.log(...args)
  }

  useEffect(() => {
    const loadPortfolios = async () => {
      setLoading(true)
      try {
        const res = await portfolio.list()
        const data = res.data.results !== undefined ? res.data.results : res.data
        setPortfolios(data)
        log('Loaded portfolios:', data.length)
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to load portfolios')
        log('Error loading portfolios:', err.message)
      } finally {
        setLoading(false)
      }
    }
    loadPortfolios()
  }, [])

  useEffect(() => {
    if (!selectedPortfolio) {
      setHoldings([])
      setPerformance(null)
      setHeatmapData([])
      return
    }

    const loadPortfolioData = async () => {
      setLoading(true)
      try {
        const [holdingsRes, dateRangeRes] = await Promise.all([
          portfolio.holdings(selectedPortfolio),
          portfolio.dateRange(selectedPortfolio),
        ])
        const holdingsData = holdingsRes.data.results !== undefined ? holdingsRes.data.results : holdingsRes.data
        setHoldings(holdingsData)
        log('Loaded holdings:', holdingsData.length)

        if (dateRangeRes.data?.min_date && dateRangeRes.data?.max_date) {
          setStartDate(dateRangeRes.data.min_date)
          setEndDate(dateRangeRes.data.max_date)
        }
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to load portfolio data')
        log('Error loading holdings:', err.message)
      } finally {
        setLoading(false)
      }
    }
    loadPortfolioData()
  }, [selectedPortfolio])

  useEffect(() => {
    if (!selectedPortfolio || !startDate || !endDate) {
      return
    }

    const loadPerformance = async () => {
      try {
        const [perfRes, heatmapRes] = await Promise.all([
          portfolio.performance(selectedPortfolio, { start_date: startDate, end_date: endDate }),
          portfolio.heatmap(selectedPortfolio),
        ])
        setPerformance(perfRes.data)
        setHeatmapData(heatmapRes.data)
        log('Performance loaded:', perfRes.data.total_invested, perfRes.data.total_current_value)
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to load performance')
        log('Error loading performance:', err.message)
      }
    }
    loadPerformance()
  }, [selectedPortfolio, startDate, endDate])

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '-'
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD',
    }).format(value)
  }

  const formatPercent = (value) => {
    if (value === null || value === undefined) return '-'
    const num = Number(value)
    if (isNaN(num)) return '-'
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
  }

  const getPerformanceChartData = () => {
    if (!performance?.daily_values) return { labels: [], datasets: [] }
    return {
      labels: performance.daily_values.map(d => d.date),
      datasets: [
        {
          label: 'Portfolio Value',
          data: performance.daily_values.map(d => d.value),
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
        },
      ],
    }
  }

  const getHeatmapChartData = () => {
    return {
      labels: heatmapData.map(d => d.symbol),
      datasets: [
        {
          label: 'Return %',
          data: heatmapData.map(d => d.gain_loss_pct || 0),
          backgroundColor: heatmapData.map(d => {
            if (d.gain_loss_pct > 0) return 'rgba(34, 197, 94, 0.8)'
            if (d.gain_loss_pct < 0) return 'rgba(239, 68, 68, 0.8)'
            return 'rgba(107, 114, 128, 0.8)'
          }),
        },
      ],
    }
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div style={{
        backgroundColor: '#fffbeb',
        border: '1px solid #fbbf24',
        borderRadius: '0.5rem',
        padding: '0.75rem',
        marginBottom: '1rem',
        fontSize: '0.875rem',
        fontFamily: 'monospace'
      }}>
        <div style={{ fontWeight: 'bold' }}>Debug State:</div>
        <div>loading: {String(loading)}</div>
        <div>portfolios count: {portfolios.length}</div>
        <div>selectedPortfolio: {selectedPortfolio || 'none'}</div>
        <div>startDate: '{startDate}'</div>
        <div>endDate: '{endDate}'</div>
        <div>error: {error || 'none'}</div>
        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
          <div style={{ fontWeight: 'bold' }}>Log:</div>
          {debug.slice(-5).map((d, i) => (
            <div key={i} style={{ whiteSpace: 'pre-wrap' }}>{d}</div>
          ))}
        </div>
      </div>

      {loading && (!Array.isArray(portfolios) || !portfolios.length) && (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-500">Loading...</div>
        </div>
      )}
        <h1 className="text-2xl font-bold">Portfolio</h1>
        
        <div className="flex gap-4 items-center">
          <select
            id="portfolio-select"
            value={selectedPortfolio || ''}
            onChange={(e) => setSelectedPortfolio(Number(e.target.value))}
            className="border rounded px-3 py-2"
          >
            <option value="">Select Portfolio</option>
            {Array.isArray(portfolios) && portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.account_type} #{p.id} ({p.holdings_count} holdings)
              </option>
            ))}
          </select>

          <div className="flex gap-2">
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="border rounded px-3 py-2"
              placeholder="Start Date"
            />
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="border rounded px-3 py-2"
              placeholder="End Date"
            />
          </div>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">
            {error}
          </div>
        )}

      {performance && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Total Invested</div>
            <div className="text-xl font-semibold">
              {formatCurrency(performance.total_invested)}
            </div>
          </div>
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Current Value</div>
            <div className="text-xl font-semibold">
              {formatCurrency(performance.total_current_value)}
            </div>
          </div>
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Gain/Loss</div>
            <div
              className={`text-xl font-semibold ${
                performance.total_gain_loss >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {formatCurrency(performance.total_gain_loss)}
            </div>
          </div>
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Return %</div>
            <div
              className={`text-xl font-semibold ${
                performance.total_gain_loss_pct >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {formatPercent(performance.total_gain_loss_pct)}
            </div>
          </div>
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <div className="text-sm text-gray-500">Dividends</div>
            <div className="text-xl font-semibold text-green-600">
              {formatCurrency(performance.total_dividends)}
            </div>
          </div>
        </div>
      )}

      {performance?.daily_values?.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Performance Over Time</h2>
          <div className="h-64">
            <Line
              data={getPerformanceChartData()}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  y: {
                    beginAtZero: false,
                    ticks: {
                      callback: (value) => formatCurrency(value),
                    },
                  },
                },
                plugins: {
                  tooltip: {
                    callbacks: {
                      label: (context) => formatCurrency(context.raw),
                    },
                  },
                },
              }}
            />
          </div>
        </div>
      )}

      {Array.isArray(heatmapData) && heatmapData.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-6 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Holdings Performance</h2>
          <div className="h-80">
            <Bar
              data={getHeatmapChartData()}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                  tooltip: {
                    callbacks: {
                      label: (context) => {
                        const data = heatmapData.find(d => d.symbol === context.label)
                        return [
                          `Symbol: ${context.label}`,
                          `Value: ${formatCurrency(data?.value || 0)}`,
                          `Return: ${formatPercent(data?.gain_loss_pct || 0)}`,
                        ]
                      },
                    },
                  },
                  legend: {
                    display: false,
                  },
                },
                scales: {
                  x: {
                    ticks: {
                      callback: (value) => formatPercent(value),
                    },
                  },
                },
              }}
            />
          </div>
          <div className="mt-2 flex gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-red-500 rounded"></div>
              <span>Negative Return</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-gray-500 rounded"></div>
              <span>Neutral</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded"></div>
              <span>Positive Return</span>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
        <h2 className="text-lg font-semibold p-4 border-b">Current Holdings</h2>
        {(!holdings || holdings.length === 0) ? (
          <div className="p-8 text-center text-gray-500">
            No holdings found. Import transactions first.
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
                    Avg Cost
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Total Cost
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Current Price
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Current Value
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Gain/Loss
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Return %
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-gray-600">
                    Dividends
                  </th>
                </tr>
              </thead>
              <tbody>
                {Array.isArray(holdings) && holdings.map((holding, idx) => (
                  <tr key={idx} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{holding.symbol}</td>
                    <td className="px-4 py-3 text-right">
                      {holding.total_shares?.toFixed(4) || '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.avg_cost)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.total_cost)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.current_price)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {formatCurrency(holding.current_value)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right ${
                        holding.gain_loss >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {formatCurrency(holding.gain_loss)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right ${
                        holding.gain_loss_pct >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}
                    >
                      {formatPercent(holding.gain_loss_pct)}
                    </td>
                    <td className="px-4 py-3 text-right text-green-600">
                      {formatCurrency(holding.dividends_received)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
