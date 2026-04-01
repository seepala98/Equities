export default function StatCard({ label, value, sub, color = 'blue' }) {
  const colors = {
    blue:  'bg-blue-50 border-blue-200 text-blue-800',
    green: 'bg-green-50 border-green-200 text-green-800',
    red:   'bg-red-50 border-red-200 text-red-800',
    gray:  'bg-gray-50 border-gray-200 text-gray-800',
  }
  return (
    <div className={`border rounded-lg p-4 ${colors[color] ?? colors.blue}`}>
      <p className="text-sm font-medium opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value ?? '—'}</p>
      {sub && <p className="text-xs mt-1 opacity-60">{sub}</p>}
    </div>
  )
}
