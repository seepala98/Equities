import { useEffect, useState } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend
} from 'chart.js'
import { listings } from '../api'
import Spinner from '../components/Spinner'
import ErrorAlert from '../components/ErrorAlert'
import StatCard from '../components/StatCard'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    listings.assetSummary()
      .then(r => setSummary(r.data))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />
  if (error) return <ErrorAlert message={error} />

  // Roll up total counts per asset_type across exchanges
  const typeTotals = {}
  let grandTotal = 0
  ;(summary || []).forEach(row => {
    typeTotals[row.asset_type] = (typeTotals[row.asset_type] || 0) + row.count
    grandTotal += row.count
  })

  const sorted = Object.entries(typeTotals).sort((a, b) => b[1] - a[1])
  const chartData = {
    labels: sorted.map(([t]) => t),
    datasets: [{
      label: 'Listings',
      data: sorted.map(([, c]) => c),
      backgroundColor: 'rgba(59, 130, 246, 0.7)',
      borderColor: 'rgba(29, 78, 216, 1)',
      borderWidth: 1,
    }],
  }
  const chartOptions = {
    responsive: true,
    plugins: { legend: { display: false }, title: { display: true, text: 'Listings by Asset Type' } },
  }

  // Exchange breakdown
  const exchangeTotals = {}
  ;(summary || []).forEach(row => {
    exchangeTotals[row.exchange] = (exchangeTotals[row.exchange] || 0) + row.count
  })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Listings" value={grandTotal.toLocaleString()} color="blue" />
        <StatCard label="Stocks" value={(typeTotals['STOCK'] || 0).toLocaleString()} color="green" />
        <StatCard label="ETFs" value={(typeTotals['ETF'] || 0).toLocaleString()} color="blue" />
        <StatCard label="Other Types" value={(grandTotal - (typeTotals['STOCK'] || 0) - (typeTotals['ETF'] || 0)).toLocaleString()} color="gray" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {Object.entries(exchangeTotals).map(([ex, count]) => (
          <StatCard key={ex} label={ex} value={count.toLocaleString()} sub="listings" color="gray" />
        ))}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 max-w-2xl">
        <Bar data={chartData} options={chartOptions} />
      </div>
    </div>
  )
}
