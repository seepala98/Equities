import { useEffect, useState, useCallback } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
} from '@tanstack/react-table'
import { listings } from '../api'
import Spinner from '../components/Spinner'
import ErrorAlert from '../components/ErrorAlert'

const ASSET_TYPES = [
  'STOCK','ETF','MUTUAL_FUND','REIT','TRUST','BOND',
  'WARRANT','RIGHTS','PREFERRED','UNIT','CRYPTO','COMMODITY','OTHER',
]
const EXCHANGES = ['TSX', 'TSXV', 'CSE']

const columns = [
  { accessorKey: 'symbol', header: 'Symbol', cell: info => <span className="font-mono font-semibold">{info.getValue()}</span> },
  { accessorKey: 'name', header: 'Name', cell: info => <span className="truncate block max-w-xs">{info.getValue()}</span> },
  { accessorKey: 'exchange', header: 'Exchange' },
  {
    accessorKey: 'asset_type',
    header: 'Type',
    cell: info => (
      <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{info.getValue()}</span>
    ),
  },
  { accessorKey: 'status', header: 'Status' },
]

export default function Listings() {
  const [data, setData] = useState([])
  const [count, setCount] = useState(0)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ search: '', exchange: '', asset_type: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const pageSize = 50

  const fetch = useCallback(() => {
    setLoading(true)
    setError(null)
    const params = {
      page,
      page_size: pageSize,
      ...(filters.search && { search: filters.search }),
      ...(filters.exchange && { exchange: filters.exchange }),
      ...(filters.asset_type && { asset_type: filters.asset_type }),
    }
    listings.list(params)
      .then(r => {
        setData(r.data.results || r.data)
        setCount(r.data.count || (r.data.results || r.data).length)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [page, filters])

  useEffect(() => { fetch() }, [fetch])

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil(count / pageSize),
  })

  const handleFilterChange = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
  }

  const totalPages = Math.ceil(count / pageSize)

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Exchange Listings</h1>

      <div className="flex gap-3 mb-4 flex-wrap">
        <input
          className="border rounded px-3 py-2 text-sm w-56"
          placeholder="Search symbol or name…"
          value={filters.search}
          onChange={e => handleFilterChange('search', e.target.value)}
        />
        <select
          className="border rounded px-3 py-2 text-sm"
          value={filters.exchange}
          onChange={e => handleFilterChange('exchange', e.target.value)}
        >
          <option value="">All Exchanges</option>
          {EXCHANGES.map(ex => <option key={ex} value={ex}>{ex}</option>)}
        </select>
        <select
          className="border rounded px-3 py-2 text-sm"
          value={filters.asset_type}
          onChange={e => handleFilterChange('asset_type', e.target.value)}
        >
          <option value="">All Types</option>
          {ASSET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <p className="text-sm text-gray-500 mb-3">
        {loading ? 'Loading…' : `${count.toLocaleString()} results`}
      </p>

      <ErrorAlert message={error} />
      {loading && <Spinner />}

      {!loading && (
        <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id}>
                  {hg.headers.map(h => (
                    <th key={h.id} className="px-4 py-3 text-left font-semibold text-gray-600">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map(row => (
                <tr key={row.id} className="border-b border-gray-50 hover:bg-gray-50">
                  {row.getVisibleCells().map(cell => (
                    <td key={cell.id} className="px-4 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
              {data.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No results.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex gap-2 items-center mt-4">
          <button
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 border rounded text-sm disabled:opacity-40"
          >
            &laquo; Prev
          </button>
          <span className="text-sm">Page {page} of {totalPages}</span>
          <button
            disabled={page === totalPages}
            onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 border rounded text-sm disabled:opacity-40"
          >
            Next &raquo;
          </button>
        </div>
      )}
    </div>
  )
}
