import { useState, useEffect } from 'react'
import { portfolio } from '../api'

export default function SimplePortfolio() {
  const [portfolios, setPortfolios] = useState([])

  useEffect(() => {
    console.log('Fetching portfolios...')
    portfolio.list()
      .then(response => {
        console.log('API response:', response)
        let data = []
        if (Array.isArray(response.data)) {
          data = response.data
        } else if (response.data && Array.isArray(response.data.results)) {
          data = response.data.results
        }
        console.log('Setting portfolios:', data)
        setPortfolios(data)
      })
      .catch(error => {
        console.error('Error fetching portfolios:', error)
      })
  }, [])

  return (
    <div>
      <h1>Simple Portfolio Test</h1>
      <div>Portfolios count: {portfolios.length}</div>
      {portfolios.map(p => (
        <div key={p.id}>Portfolio {p.id}: {p.name}</div>
      ))}
    </div>
  )
}