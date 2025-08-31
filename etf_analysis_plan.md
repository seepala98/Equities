# ETF Performance Analysis System

## 🎯 Investment Performance Calculator

### Core Question: 
"How would $10,000 invested in ETF X on date Y perform today?"

## 📊 Required Data Points:

### Historical Prices:
- Daily OHLCV data
- **Adjusted Close** (accounts for dividends/splits)
- Dividend/distribution dates and amounts

### ETF Fundamentals:
- Management Expense Ratio (MER)
- Assets Under Management (AUM)
- Inception date
- Holdings breakdown
- Benchmark index

## 🏗️ Technical Implementation:

### 1. Database Schema Extensions:
```sql
-- ETF metadata table
CREATE TABLE etf_info (
    symbol VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255),
    mer DECIMAL(5,4),        -- Management Expense Ratio
    aum BIGINT,              -- Assets Under Management
    inception_date DATE,
    category VARCHAR(100),
    benchmark VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ETF daily performance (extends existing Stock model)
CREATE TABLE etf_performance (
    symbol VARCHAR(32),
    date DATE,
    adjusted_close DECIMAL(12,4),    -- Critical for dividends!
    dividend DECIMAL(8,4) DEFAULT 0, -- Daily dividend amount
    total_return DECIMAL(12,6),      -- Cumulative total return
    PRIMARY KEY (symbol, date)
);
```

### 2. Performance Calculation Logic:
```python
def calculate_investment_performance(symbol: str, initial_investment: float, 
                                   start_date: str, end_date: str = None):
    """
    Calculate how $X invested on start_date would perform today.
    
    Returns:
    - Final value
    - Total return %
    - Annualized return %
    - Dividend income
    """
    # Get price on start_date (adjusted for splits/dividends)
    start_price = get_adjusted_close(symbol, start_date)
    
    # Calculate shares purchased
    shares = initial_investment / start_price
    
    # Get current/end price
    end_price = get_adjusted_close(symbol, end_date or today())
    
    # Calculate final value
    final_value = shares * end_price
    
    # Add dividend income
    dividend_income = calculate_dividend_income(symbol, shares, start_date, end_date)
    
    total_final = final_value + dividend_income
    
    return {
        'initial_investment': initial_investment,
        'final_value': total_final,
        'total_return_pct': ((total_final - initial_investment) / initial_investment) * 100,
        'dividend_income': dividend_income,
        'shares_owned': shares,
        'years_held': calculate_years_between(start_date, end_date)
    }
```

## 📈 Popular Canadian ETFs to Track:

### Broad Market:
- **VTI.TO** - Vanguard Total Stock Market
- **XGRO.TO** - iShares Core Growth ETF
- **VEQT.TO** - Vanguard All Equity ETF

### Sector-Specific:
- **TDB902.TO** - TD Canadian Index
- **XIC.TO** - iShares TSX Capped Composite
- **VFV.TO** - Vanguard S&P 500

### Bond ETFs:
- **VAB.TO** - Vanguard Canadian Aggregate Bond
- **XBB.TO** - iShares Core Canadian Universe Bond

## 🚀 Implementation Phases:

### Phase 1: Data Collection (Week 1)
- Extend current yfinance integration
- Create ETF-specific scraping logic
- Set up historical data backfill

### Phase 2: Performance Engine (Week 2)  
- Build investment calculator
- Implement dividend tracking
- Create performance analytics

### Phase 3: Web Interface (Week 3)
- Build ETF search and comparison
- Create investment scenario calculator
- Add performance visualization

### Phase 4: Advanced Analytics (Week 4)
- Portfolio allocation analysis
- Risk metrics (Sharpe ratio, volatility)
- Benchmark comparison tools
