import { useEffect, useState } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler
} from 'chart.js'
import { etfs } from '../api'
import Spinner from '../components/Spinner'
import ErrorAlert from '../components/ErrorAlert'
import StatCard from '../components/StatCard'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const TODAY = new Date().toISOString().split('T')[0]
const FIVE_YEARS_AGO = new Date(Date.now() - 5 * 365.25 * 24 * 3600 * 1000).toISOString().split('T')[0]

export default function ETFAnalysis() {
  const [popularEtfs, setPopularEtfs] = useState({})
  const [form, setForm] = useState({ symbol: '', investment_amount: '10000', start_date: FIVE_YEARS_AGO, end_date: '' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    etfs.popular().then(r => setPopularEtfs(r.data)).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const params = { ...form }
      if (!params.end_date) delete params.end_date
      const r = await etfs.performance(params)
      setResult(r.data)
    } catch (err) {
      setError(err.response?.data?.error || err.message)
    } finally {
      setLoading(false)
    }
  }

  // Growth chart: simple 2-point line (start vs end value)
  const chartData = result ? {
    labels: [result.start_date, result.end_date],
    datasets: [
      {
        label: 'Portfolio Value ($)',
        data: [result.initial_investment, result.total_final_value],
        borderColor: result.total_return_dollars >= 0 ? 'rgba(34,197,94,1)' : 'rgba(239,68,68,1)',
        backgroundColor: result.total_return_dollars >= 0 ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 6,
      },
    ],
  } : null

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">ETF Performance Analysis</h1>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6 max-w-xl">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">ETF Symbol</label>
            <input
              className="w-full border rounded px-3 py-2 text-sm"
              value={form.symbol}
              onChange={e => setForm(f => ({ ...f, symbol: e.target.value.toUpperCase() }))}
              placeholder="e.g. XGRO, VEQT, VFV"
              required
            />
            {Object.keys(popularEtfs).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {Object.entries(popularEtfs).slice(0, 6).map(([sym, name]) => (
                  <button
                    key={sym}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, symbol: sym }))}
                    className="text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 px-2 py-1 rounded"
                    title={name}
                  >
                    {sym}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Initial Investment ($)</label>
            <input
              type="number"
              min="1"
              className="w-full border rounded px-3 py-2 text-sm"
              value={form.investment_amount}
              onChange={e => setForm(f => ({ ...f, investment_amount: e.target.value }))}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Start Date</label>
              <input
                type="date"
                className="w-full border rounded px-3 py-2 text-sm"
                value={form.start_date}
                onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">End Date (optional)</label>
              <input
                type="date"
                className="w-full border rounded px-3 py-2 text-sm"
                value={form.end_date}
                max={TODAY}
                onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))}
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 rounded disabled:opacity-50"
          >
            {loading ? 'Calculating…' : 'Calculate'}
          </button>
        </form>
      </div>

      <ErrorAlert message={error} />

      {loading && <Spinner />}

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Initial Investment" value={`$${Number(result.initial_investment).toLocaleString()}`} color="gray" />
            <StatCard label="Final Value" value={`$${Number(result.total_final_value).toLocaleString()}`} color="blue" />
            <StatCard
              label="Total Return"
              value={`${result.total_return_percent >= 0 ? '+' : ''}${result.total_return_percent}%`}
              sub={`$${result.total_return_dollars >= 0 ? '+' : ''}${Number(result.total_return_dollars).toLocaleString()}`}
              color={result.total_return_dollars >= 0 ? 'green' : 'red'}
            />
            <StatCard
              label="Annualized Return"
              value={`${result.annualized_return_percent >= 0 ? '+' : ''}${result.annualized_return_percent}%`}
              sub={`${result.years_held} years held`}
              color={result.annualized_return_percent >= 0 ? 'green' : 'red'}
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <StatCard label="Shares Purchased" value={result.shares_purchased} color="gray" />
            <StatCard label="Start Price" value={`$${result.start_price}`} color="gray" />
            <StatCard label="End Price" value={`$${result.end_price}`} color="gray" />
            <StatCard label="Dividend Income" value={`$${Number(result.dividend_income).toLocaleString()}`} color="green" />
          </div>
          {chartData && (
            <div className="bg-white border border-gray-200 rounded-lg p-6 max-w-lg">
              <Line data={chartData} options={{ responsive: true, plugins: { legend: { display: false } } }} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
