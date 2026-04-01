import { useEffect, useState } from 'react'
import { Doughnut } from 'react-chartjs-2'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { sectors } from '../api'
import Spinner from '../components/Spinner'
import ErrorAlert from '../components/ErrorAlert'

ChartJS.register(ArcElement, Tooltip, Legend)

const SECTOR_KEYS = {
  'technology': 'Technology',
  'healthcare': 'Healthcare',
  'financial-services': 'Financial Services',
  'consumer-cyclical': 'Consumer Cyclical',
  'communication-services': 'Communication Services',
  'industrials': 'Industrials',
  'consumer-defensive': 'Consumer Defensive',
  'energy': 'Energy',
  'basic-materials': 'Basic Materials',
  'real-estate': 'Real Estate',
  'utilities': 'Utilities',
}

export default function SectorAnalysis() {
  const [sectorList, setSectorList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error] = useState(null)

  useEffect(() => {
    sectors.list()
      .then(r => setSectorList(r.data.results || r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  const chartData = sectorList.length ? {
    labels: sectorList.map(s => s.sector_name),
    datasets: [{
      data: sectorList.map(() => 1), // equal slices as placeholder
      backgroundColor: [
        '#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6',
        '#06b6d4','#f97316','#84cc16','#ec4899','#6366f1','#14b8a6',
      ],
    }],
  } : null

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Sector Analysis</h1>

      <ErrorAlert message={error} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold mb-4">Available Sectors</h2>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(SECTOR_KEYS).map(([key, name]) => (
              <div key={key} className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm">
                <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
                {name}
              </div>
            ))}
          </div>
        </div>

        {sectorList.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h2 className="font-semibold mb-4">Sectors in Database ({sectorList.length})</h2>
            {chartData && (
              <div className="w-64 mx-auto">
                <Doughnut
                  data={chartData}
                  options={{ plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } } }}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {sectorList.length > 0 && (
        <div className="mt-6 bg-white border border-gray-200 rounded-lg p-6">
          <h2 className="font-semibold mb-3">Sector Details</h2>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-2 text-left">Sector</th>
                <th className="px-4 py-2 text-left">Code</th>
                <th className="px-4 py-2 text-left">Description</th>
              </tr>
            </thead>
            <tbody>
              {sectorList.map(s => (
                <tr key={s.id} className="border-b border-gray-50">
                  <td className="px-4 py-2 font-medium">{s.sector_name}</td>
                  <td className="px-4 py-2 font-mono text-gray-500">{s.sector_code || '—'}</td>
                  <td className="px-4 py-2 text-gray-600">{s.description || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
