import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { portfolio } from '../api'

export default function ImportPortfolio() {
  const [file, setFile] = useState(null)
  const [parsedData, setParsedData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [accountType, setAccountType] = useState('TFSA')
  const [accountNumber, setAccountNumber] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return

    setFile(acceptedFiles)
    setLoading(true)
    setError(null)
    setParsedData(null)
    setImportResult(null)

    try {
      let data
      if (acceptedFiles.length > 1) {
        // Multi-file upload: PDF + CSV
        const response = await portfolio.parseMultiple(acceptedFiles)
        data = response.data
      } else {
        // Single file
        const response = await portfolio.parse(acceptedFiles[0])
        data = response.data
      }

      if (data.error) {
        setError(data.error)
        return
      }

      setParsedData(data)

      if (data.detected_account_type) {
        setAccountType(data.detected_account_type)
      }
      if (data.detected_account_number) {
        setAccountNumber(data.detected_account_number)
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to parse file')
    } finally {
      setLoading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  })

  const handleImport = async () => {
    if (!parsedData || !file) return

    setImporting(true)
    setError(null)

    try {
      const portfolioName = accountType
      const fileNames = Array.isArray(file) ? file.map(f => f.name).join(', ') : file?.name || ''
      const response = await portfolio.create({
        name: portfolioName,
        account_type: accountType,
        account_number: accountNumber,
        transactions: parsedData.transactions,
        holdings: parsedData.holdings || [],
        cash_summary: parsedData.cash_summary || {},
        stock_lending: parsedData.stock_lending || [],
        source_file: fileNames,
        statement_period: parsedData.statement_period,
      })

      setImportResult(response.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to import transactions')
    } finally {
      setImporting(false)
    }
  }

  const deleteTransaction = (index) => {
    const newTransactions = [...parsedData.transactions]
    newTransactions.splice(index, 1)
    setParsedData({
      ...parsedData,
      transactions: newTransactions,
      summary: {
        ...parsedData.summary,
        total_transactions: newTransactions.length,
      },
    })
  }

  const formatCurrency = (value) => {
    if (value === null || value === undefined) return '-'
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency: 'CAD',
    }).format(value)
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    // Parse as local date to avoid timezone issues
    const [year, month, day] = dateStr.split('-').map(Number)
    const date = new Date(year, month - 1, day)
    return date.toLocaleDateString('en-CA')
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Import Portfolio</h1>

      {importResult ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-green-800 mb-2">
            Import Successful!
          </h2>
          <p className="text-green-700">
            Imported {importResult.imported_count} transactions into {importResult.portfolio?.name}
          </p>
          <button
            onClick={() => {
              setFile(null)
              setParsedData(null)
              setImportResult(null)
              setAccountNumber('')
            }}
            className="mt-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            Import Another File
          </button>
        </div>
      ) : (
        <>
          {!parsedData && (
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <input {...getInputProps()} />
              {loading ? (
                <p className="text-gray-600">Parsing file...</p>
              ) : (
                <>
                  <p className="text-lg mb-2">
                    Drag & drop a CSV or PDF file here
                  </p>
                  <p className="text-sm text-gray-500">
                    Supports Wealthsimple monthly statements (FHSA, TFSA)
                  </p>
                </>
              )}
            </div>
          )}

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          )}

          {parsedData && (
            <div className="mt-6">
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <h2 className="text-lg font-semibold mb-4">Import Preview</h2>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Account Type
                    </label>
                    <select
                      value={accountType}
                      onChange={(e) => setAccountType(e.target.value)}
                      className="w-full border rounded px-3 py-2"
                    >
                      <option value="TFSA">TFSA - Tax-Free Savings Account</option>
                      <option value="FHSA">FHSA - First Home Savings Account</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Account Number
                    </label>
                    <input
                      type="text"
                      value={accountNumber}
                      onChange={(e) => setAccountNumber(e.target.value)}
                      placeholder="Auto-detected or enter manually"
                      className="w-full border rounded px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Statement Period
                    </label>
                    <input
                      type="text"
                      value={parsedData.statement_period || 'Unknown'}
                      disabled
                      className="w-full border rounded px-3 py-2 bg-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Source File
                    </label>
                    <input
                      type="text"
                      value={file?.name || ''}
                      disabled
                      className="w-full border rounded px-3 py-2 bg-gray-100"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
                  <div className="bg-blue-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.summary?.buys || 0}</div>
                    <div>BUYs</div>
                  </div>
                  <div className="bg-red-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.summary?.sells || 0}</div>
                    <div>SELLs</div>
                  </div>
                  <div className="bg-green-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.summary?.dividends || 0}</div>
                    <div>DIVs</div>
                  </div>
                  <div className="bg-purple-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.summary?.drips || 0}</div>
                    <div>DRIPs</div>
                  </div>
                  <div className="bg-yellow-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.holdings?.length || 0}</div>
                    <div>Holdings</div>
                  </div>
                  <div className="bg-gray-50 rounded p-2 text-center">
                    <div className="font-semibold">{parsedData.summary?.total_transactions || 0}</div>
                    <div>Total</div>
                  </div>
                </div>

                {/* Cash Summary Section */}
                {parsedData.cash_summary && Object.keys(parsedData.cash_summary).length > 0 && (
                  <div className="mt-4">
                    <h3 className="font-medium text-gray-700 mb-2">Cash Summary</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      <div className="bg-gray-50 rounded p-2">
                        <div className="text-gray-500">Closing Balance</div>
                        <div className="font-semibold">{formatCurrency(parsedData.cash_summary.closing_cash_balance)}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-2">
                        <div className="text-gray-500">Total Paid In</div>
                        <div className="font-semibold">{formatCurrency(parsedData.cash_summary.total_cash_paid_in)}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-2">
                        <div className="text-gray-500">Total Paid Out</div>
                        <div className="font-semibold">{formatCurrency(parsedData.cash_summary.total_cash_paid_out)}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-2">
                        <div className="text-gray-500">Contributions YTD</div>
                        <div className="font-semibold">{formatCurrency(parsedData.cash_summary.contributions_ytd)}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Holdings Section */}
                {parsedData.holdings && parsedData.holdings.length > 0 && (
                  <div className="mt-4">
                    <h3 className="font-medium text-gray-700 mb-2">Holdings ({parsedData.holdings.length})</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full bg-white border rounded-lg">
                        <thead className="bg-gray-100">
                          <tr>
                            <th className="px-3 py-2 text-left text-sm font-medium">Symbol</th>
                            <th className="px-3 py-2 text-left text-sm font-medium">Name</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Qty</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Price</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Market Value</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Book Cost</th>
                          </tr>
                        </thead>
                        <tbody>
                          {parsedData.holdings.map((h, idx) => (
                            <tr key={idx} className="border-t">
                              <td className="px-3 py-2 text-sm font-medium">{h.symbol}</td>
                              <td className="px-3 py-2 text-sm text-gray-600">{h.name?.substring(0, 30)}</td>
                              <td className="px-3 py-2 text-sm text-right">{h.quantity}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatCurrency(h.price)}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatCurrency(h.market_value)}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatCurrency(h.book_cost)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Stock Lending Section */}
                {parsedData.stock_lending && parsedData.stock_lending.length > 0 && (
                  <div className="mt-4">
                    <h3 className="font-medium text-gray-700 mb-2">Stock Lending ({parsedData.stock_lending.length})</h3>
                    <div className="overflow-x-auto">
                      <table className="min-w-full bg-white border rounded-lg">
                        <thead className="bg-gray-100">
                          <tr>
                            <th className="px-3 py-2 text-left text-sm font-medium">Symbol</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Collateral (CAD)</th>
                            <th className="px-3 py-2 text-right text-sm font-medium">Loan Value (CAD)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {parsedData.stock_lending.map((s, idx) => (
                            <tr key={idx} className="border-t">
                              <td className="px-3 py-2 text-sm font-medium">{s.symbol}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatCurrency(s.collateral_cad)}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatCurrency(s.loan_value_cad)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="min-w-full bg-white border rounded-lg">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium">Date</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Type</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Symbol</th>
                      <th className="px-4 py-2 text-right text-sm font-medium">Qty</th>
                      <th className="px-4 py-2 text-right text-sm font-medium">Price</th>
                      <th className="px-4 py-2 text-right text-sm font-medium">Amount</th>
                      <th className="px-4 py-2 text-left text-sm font-medium">Description</th>
                      <th className="px-4 py-2 text-center text-sm font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsedData.transactions.map((tx, index) => (
                      <tr key={index} className={tx.warnings?.length > 0 ? 'bg-yellow-50' : ''}>
                        <td className="px-4 py-2 text-sm">{formatDate(tx.date)}</td>
                        <td className="px-4 py-2 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              tx.transaction_type === 'BUY'
                                ? 'bg-blue-100 text-blue-800'
                                : tx.transaction_type === 'SELL'
                                ? 'bg-red-100 text-red-800'
                                : tx.transaction_type === 'DIV' || tx.transaction_type === 'DRIP'
                                ? 'bg-green-100 text-green-800'
                                : 'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {tx.transaction_type}
                            {tx.is_drip && ' (DRIP)'}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-sm font-medium">{tx.symbol || '-'}</td>
                        <td className="px-4 py-2 text-sm text-right">
                          {tx.quantity ? tx.quantity : '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-right">
                          {tx.price ? formatCurrency(tx.price) : '-'}
                        </td>
                        <td
                          className={`px-4 py-2 text-sm text-right ${
                            tx.amount > 0 ? 'text-green-600' : 'text-red-600'
                          }`}
                        >
                          {formatCurrency(tx.amount)}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-600 max-w-xs truncate">
                          {tx.description}
                        </td>
                        <td className="px-4 py-2 text-center">
                          <button
                            onClick={() => deleteTransaction(index)}
                            className="text-red-600 hover:text-red-800 text-sm"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {parsedData.transactions.some((tx) => tx.warnings?.length > 0) && (
                <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h3 className="font-medium text-yellow-800 mb-2">Warnings</h3>
                  <ul className="list-disc list-inside text-sm text-yellow-700">
                    {parsedData.transactions
                      .filter((tx) => tx.warnings?.length > 0)
                      .map((tx, idx) => (
                        <li key={idx}>
                          Row {idx + 1} ({tx.symbol}): {tx.warnings.join(', ')}
                        </li>
                      ))}
                  </ul>
                </div>
              )}

              <div className="mt-6 flex gap-4">
                <button
                  onClick={handleImport}
                  disabled={importing || parsedData.transactions.length === 0}
                  className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {importing ? 'Importing...' : 'Confirm Import'}
                </button>
                <button
                  onClick={() => {
                    setFile(null)
                    setParsedData(null)
                    setError(null)
                  }}
                  className="px-6 py-2 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
