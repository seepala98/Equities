import { useState, useEffect } from 'react'
import { portfolio } from '../api'

export default function TestPortfolio() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    portfolio.list().then(res => {
      console.log('API response:', res)
      setData(res.data)
    }).catch(err => {
      console.error('API error:', err)
      setError(err.message)
    })
  }, [])

  return (
    <div>
      <h1>Test Portfolio</h1>
      {error && <div>Error: {error}</div>}
      {data && <div>Data: {JSON.stringify(data)}</div>}
      {!data && !error && <div>Loading...</div>}
    </div>
  )
}