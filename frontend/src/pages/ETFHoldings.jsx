import { useEffect, useState } from 'react'
import { Doughnut } from 'react-chartjs-2'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { etfs } from '../api'
import Spinner from '../components/Spinner'
import ErrorAlert from '../components/ErrorAlert'

ChartJS.register(ArcElement, Tooltip, Legend)

const PALETTE = [
  '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
  '#06b6d4','#f97316','#84cc16','#ec4899','#6366f1',
]

export default function ETFHoldings() {
  const [popularEtfs, setPopularEtfs] = useState({})
  const [symbol, setSymbol] = useState('')
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [fetchMsg, setFetchMsg] = useState(null)

  useEffect(() => {
    etfs.popular().then(r => setPopularEtfs(r.data)).catch(() => {})
  }, [])

  const load = async (sym) => {
    setLoading(true)
    setError(null)
    setDetail(null)
    try {
      const r = await etfs.detail(sym)
      setDetail(r.data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFetch = async (sym) => {
    setFetching(true)
    setFetchMsg(null)
    try {
      const r = await etfs.fetch(sym)
      setFetchMsg(r.data.message)
      await load(sym)
    } catch (err) {
      setFetchMsg(err.response?.data?.message || err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (symbol) load(symbol.toUpperCase())
  }

  const holdingsChartData = detail?.holdings?.length ? {
    labels: detail.holdings.slice(0, 10).map(h => h.stock_symbol),
    datasets: [{
      data: detail.holdings.slice(0, 10).map(h => h.weight_percentage),
      backgroundColor: PALETTE,
    }],
  } : null

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">ETF Holdings</h1>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6 max-w-xl">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            className="flex-1 border rounded px-3 py-2 text-sm"
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            placeholder="Enter ETF symbol (e.g. XGRO)"
          />
          <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded text-sm">
            View
          </button>
          <button
            type="button"
            disabled={!symbol || fetching}
            onClick={() => handleFetch(symbol)}
            className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded text-sm disabled:opacity-50"
          >
            {fetching ? '…' : 'Refresh'}
          </button>
        </form>

        {Object.keys(popularEtfs).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {Object.entries(popularEtfs).slice(0, 8).map(([sym, name]) => (
              <button
                key={sym}
                onClick={() => { setSymbol(sym); load(sym) }}
                className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 px-2 py-1 rounded"
                title={name}
              >
                {sym}
              </button>
            ))}
          </div>
        )}
      </div>

      {fetchMsg && <div className="mb-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded px-4 py-2">{fetchMsg}</div>}
      <ErrorAlert message={error} />
      {loading && <Spinner />}

      {detail && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-1">{detail.symbol} — {detail.name}</h2>
            <div className="flex gap-6 text-sm text-gray-600 mt-2">
              {detail.fund_family && <span>Family: <strong>{detail.fund_family}</strong></span>}
              {detail.mer_formatted && <span>MER: <strong>{detail.mer_formatted}</strong></span>}
              {detail.aum_formatted && <span>AUM: <strong>{detail.aum_formatted}</strong></span>}
              {detail.currency && <span>Currency: <strong>{detail.currency}</strong></span>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Holdings table */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold mb-3">Top Holdings ({detail.holdings?.length || 0})</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-2">Symbol</th>
                    <th className="pb-2">Name</th>
                    <th className="pb-2 text-right">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {(detail.holdings || []).slice(0, 15).map(h => (
                    <tr key={h.stock_symbol} className="border-b border-gray-50">
                      <td className="py-1 font-mono font-medium">{h.stock_symbol}</td>
                      <td className="py-1 text-gray-600 truncate max-w-[160px]">{h.stock_name}</td>
                      <td className="py-1 text-right">{h.weight_formatted}</td>
                    </tr>
                  ))}
                  {!detail.holdings?.length && (
                    <tr><td colSpan={3} className="py-4 text-gray-400 text-center">No holdings data. Click Refresh to fetch.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Doughnut chart */}
            {holdingsChartData && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col items-center">
                <h3 className="font-semibold mb-3">Top 10 Holdings Breakdown</h3>
                <div className="w-64">
                  <Doughnut
                    data={holdingsChartData}
                    options={{ plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } } }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Sector allocations */}
          {detail.sector_allocations?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold mb-3">Sector Allocations</h3>
              <div className="space-y-2">
                {detail.sector_allocations.map(s => (
                  <div key={s.sector_name} className="flex items-center gap-3">
                    <span className="w-40 text-sm truncate">{s.sector_name}</span>
                    <div className="flex-1 bg-gray-100 rounded h-3">
                      <div
                        className="bg-blue-500 h-3 rounded"
                        style={{ width: `${Math.min(s.allocation_percentage, 100)}%` }}
                      />
                    </div>
                    <span className="text-sm w-12 text-right">{s.allocation_formatted}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
