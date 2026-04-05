import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ETFAnalysis from './pages/ETFAnalysis'
import ETFHoldings from './pages/ETFHoldings'
import Listings from './pages/Listings'
import SectorAnalysis from './pages/SectorAnalysis'
import ImportPortfolio from './pages/ImportPortfolio'
import Portfolio from './pages/Portfolio'
import PortfolioHeatmap from './pages/PortfolioHeatmap'

function NavItem({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
          isActive
            ? 'bg-brand-700 text-white'
            : 'text-gray-700 hover:bg-gray-100'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-6">
          <span className="text-lg font-bold text-brand-900 mr-4">Equities</span>
          <nav className="flex gap-1">
            <NavItem to="/" label="Dashboard" />
            <NavItem to="/portfolio" label="Portfolio" />
            <NavItem to="/portfolio/import" label="Import" />
            <NavItem to="/portfolio/heatmap" label="Heatmap" />
            <NavItem to="/etf-analysis" label="ETF Analysis" />
            <NavItem to="/etf-holdings" label="Holdings" />
            <NavItem to="/listings" label="Listings" />
            <NavItem to="/sector-analysis" label="Sectors" />
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/portfolio/import" element={<ImportPortfolio />} />
          <Route path="/portfolio/heatmap" element={<PortfolioHeatmap />} />
          <Route path="/etf-analysis" element={<ETFAnalysis />} />
          <Route path="/etf-holdings" element={<ETFHoldings />} />
          <Route path="/listings" element={<Listings />} />
          <Route path="/sector-analysis" element={<SectorAnalysis />} />
        </Routes>
      </main>
    </div>
  )
}
