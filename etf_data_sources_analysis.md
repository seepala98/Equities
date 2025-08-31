# ETF Holdings Data Sources Analysis

## 🎯 Goal: Get Complete ETF Holdings Data
- Stock symbols and names in each ETF
- Weight percentages of each holding
- Sector and geographic allocations  
- Industry classifications
- Regular updates (quarterly/monthly)

## 📊 Available Data Sources:

### 🥇 **Best Free Options:**

#### 1. **Yahoo Finance (yfinance)**
```python
import yfinance as yf
etf = yf.Ticker("XGRO.TO")
holdings = etf.get_holdings()  # Limited to top holdings
info = etf.info  # Basic fund info
```
**Pros:** 
- Already integrated in your system
- Free and reliable
- Some holdings data available

**Cons:** 
- Limited holdings (usually top 10-20)
- No detailed sector breakdowns
- Inconsistent data availability

**Rating:** ⭐⭐⭐ Good starting point

---

#### 2. **Fund Company Websites (Direct Scraping)**

**Vanguard Canada:** `https://www.vanguard.ca/`
```
https://www.vanguard.ca/advisors/products/en/detail/etf/9692/equity
```

**iShares Canada:** `https://www.ishares.com/ca/`  
```
https://www.ishares.com/ca/individual/en/products/239447/ishares-core-growth-etf-portfolio
```

**Pros:**
- Most comprehensive and accurate data
- Full holdings lists with exact percentages
- Sector and geographic allocations
- Updated regularly (monthly/quarterly)

**Cons:**
- Requires web scraping
- Different formats per fund family
- May break with website changes

**Rating:** ⭐⭐⭐⭐⭐ Best accuracy, requires work

---

#### 3. **Morningstar Canada**
```
https://www.morningstar.ca/ca/funds/snapshot/snapshot.aspx?id=F00000OXG7
```

**Pros:**
- Professional-grade analysis
- Sector allocations and style boxes
- Holdings data with percentages
- Industry classifications

**Cons:**
- Requires scraping
- May have rate limits
- Some data behind paywall

**Rating:** ⭐⭐⭐⭐ High quality data

---

### 💰 **Premium API Options:**

#### 4. **Alpha Vantage**
```python
# ETF Profile and Holdings
url = f'https://www.alphavantage.co/query?function=ETF_PROFILE&symbol=XGRO.TO&apikey={API_KEY}'
```

**Pros:**
- RESTful API with JSON responses
- ETF profiles, holdings, and performance
- 500 free requests/day

**Cons:**
- Limited free tier
- May not have all Canadian ETFs

**Rating:** ⭐⭐⭐⭐ Good for production

---

#### 5. **Financial Modeling Prep**
```python
# ETF Holdings API
url = f'https://financialmodelingprep.com/api/v4/etf-holdings/XGRO.TO?apikey={API_KEY}'
```

**Pros:**
- Comprehensive ETF data
- Holdings with weights
- 250 free requests/day

**Rating:** ⭐⭐⭐⭐ Professional option

---

### 🇨🇦 **Canadian-Specific Sources:**

#### 6. **Globe and Mail Markets**
```
https://www.theglobeandmail.com/investing/markets/etfs/
```
- Excellent ETF screener and data
- Canadian focus
- Holdings information available

#### 7. **FundLibrary.com**
```  
https://www.fundlibrary.com/MutualFunds/
```
- Canadian mutual fund and ETF database
- Detailed holdings and allocations

---

## 🚀 **Recommended Implementation Strategy:**

### Phase 1: Quick Start (This Week)
```python
# Use yfinance for basic holdings
etf = yf.Ticker("XGRO.TO") 
holdings = etf.get_holdings()
```

### Phase 2: Fund Company Scraping (Best Quality)
```python
# Custom scrapers for each major fund family
# Priority order: Vanguard → iShares → BMO → Invesco
```

### Phase 3: Professional APIs (Scale Up)
```python
# Add Alpha Vantage or Financial Modeling Prep
# For comprehensive coverage and reliability
```

## 📋 **Sample ETF Holdings Data Structure:**

```json
{
  "etf_symbol": "XGRO.TO",
  "etf_name": "iShares Core Growth ETF Portfolio", 
  "as_of_date": "2024-08-30",
  "total_holdings": 247,
  "top_holdings": [
    {
      "symbol": "ITOT",
      "name": "iShares Core S&P Total US Stock Market ETF",
      "weight": 47.8,
      "shares_held": 125000,
      "market_value": 15750000,
      "sector": "Equity ETF",
      "region": "United States"
    },
    {
      "symbol": "XIC.TO", 
      "name": "iShares Core S&P Total Canadian Stock Market ETF",
      "weight": 23.9,
      "shares_held": 85000,
      "market_value": 8500000, 
      "sector": "Equity ETF",
      "region": "Canada"
    }
  ],
  "sector_allocation": {
    "Technology": 22.5,
    "Financials": 15.2,
    "Healthcare": 12.8,
    "Consumer Discretionary": 11.1
  },
  "geographic_allocation": {
    "United States": 47.8,
    "Canada": 23.9,
    "International Developed": 24.1,
    "Emerging Markets": 4.2
  }
}
```

## 🛠️ **Technical Implementation:**

### For Your Current System:
1. **Start with yfinance** (immediate)
2. **Add Vanguard/iShares scrapers** (best data)
3. **Store in your new ETF tables** 
4. **Update via Airflow DAG** (weekly/monthly)
5. **Display in web interface**

### Example yfinance Integration:
```python
def get_etf_holdings(symbol):
    ticker = yf.Ticker(f"{symbol}.TO")
    
    # Get basic info
    info = ticker.info
    
    # Try to get holdings (may not work for all ETFs)
    try:
        holdings = ticker.get_holdings()
        return {
            'basic_info': info,
            'holdings': holdings,
            'success': True
        }
    except:
        return {
            'basic_info': info, 
            'holdings': None,
            'success': False
        }
```
