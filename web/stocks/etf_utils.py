"""
ETF Performance Analysis Utilities
Extends the existing stock system for ETF-specific analysis
"""
from decimal import Decimal
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
from typing import Dict, Optional, Tuple

from .models import Stock


def get_canadian_etf_ticker(symbol: str) -> str:
    """Convert ETF symbol to Yahoo Finance format for Canadian markets."""
    symbol = symbol.upper().strip()
    if not symbol.endswith('.TO'):
        symbol += '.TO'
    return symbol


def fetch_etf_info(symbol: str) -> Dict:
    """Fetch comprehensive ETF information including fundamentals."""
    ticker_symbol = get_canadian_etf_ticker(symbol)
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        info = ticker.info
        return {
            'symbol': symbol,
            'name': info.get('longName', ''),
            'category': info.get('category', ''),
            'total_assets': info.get('totalAssets', 0),
            'expense_ratio': info.get('annualHoldingsTurnover', 0),  # MER approximation
            'nav': info.get('navPrice', 0),
            'ytd_return': info.get('ytdReturn', 0),
            'three_year_avg_return': info.get('threeYearAverageReturn', 0),
            'beta': info.get('beta', 0),
            'currency': info.get('currency', 'CAD'),
        }
    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return {'symbol': symbol, 'name': f'ETF {symbol}'}


def calculate_investment_performance(
    symbol: str, 
    investment_amount: float, 
    start_date: str, 
    end_date: Optional[str] = None
) -> Dict:
    """
    Calculate investment performance for a given ETF.
    
    Args:
        symbol: ETF symbol (e.g., 'XGRO', 'VTI')
        investment_amount: Initial investment in dollars
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Dictionary with performance metrics
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    ticker_symbol = get_canadian_etf_ticker(symbol)
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # Fetch historical data with dividends
        hist = ticker.history(start=start_date, end=end_date, actions=True)
        
        if hist.empty:
            raise ValueError(f"No data available for {symbol}")
        
        # Get start and end prices (adjusted for splits/dividends)
        start_price = float(hist.iloc[0]['Close'])
        end_price = float(hist.iloc[-1]['Close'])
        
        # Calculate shares purchased
        shares_purchased = investment_amount / start_price
        
        # Calculate dividend income
        dividends = hist['Dividends'].sum() if 'Dividends' in hist.columns else 0
        dividend_income = float(dividends) * shares_purchased
        
        # Calculate final portfolio value
        final_stock_value = shares_purchased * end_price
        total_final_value = final_stock_value + dividend_income
        
        # Calculate returns
        total_return = total_final_value - investment_amount
        total_return_pct = (total_return / investment_amount) * 100
        
        # Calculate annualized return
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        years_held = (end_dt - start_dt).days / 365.25
        
        if years_held > 0:
            annualized_return = ((total_final_value / investment_amount) ** (1/years_held) - 1) * 100
        else:
            annualized_return = 0
        
        return {
            'symbol': symbol,
            'initial_investment': investment_amount,
            'start_date': start_date,
            'end_date': end_date,
            'start_price': round(start_price, 4),
            'end_price': round(end_price, 4),
            'shares_purchased': round(shares_purchased, 6),
            'dividend_income': round(dividend_income, 2),
            'final_stock_value': round(final_stock_value, 2),
            'total_final_value': round(total_final_value, 2),
            'total_return_dollars': round(total_return, 2),
            'total_return_percent': round(total_return_pct, 2),
            'annualized_return_percent': round(annualized_return, 2),
            'years_held': round(years_held, 2)
        }
        
    except Exception as e:
        raise ValueError(f"Error calculating performance for {symbol}: {e}")


def compare_etf_performance(
    symbols: list, 
    investment_amount: float, 
    start_date: str, 
    end_date: Optional[str] = None
) -> Dict:
    """Compare performance of multiple ETFs with same investment amount."""
    results = {}
    
    for symbol in symbols:
        try:
            performance = calculate_investment_performance(
                symbol, investment_amount, start_date, end_date
            )
            results[symbol] = performance
        except Exception as e:
            results[symbol] = {'error': str(e)}
    
    return results


def get_popular_canadian_etfs() -> Dict[str, str]:
    """Return a dictionary of popular Canadian ETFs for quick testing."""
    return {
        'XGRO': 'iShares Core Growth ETF Portfolio',
        'VEQT': 'Vanguard All Equity ETF Portfolio', 
        'VTI': 'Vanguard Total Stock Market ETF',
        'VFV': 'Vanguard S&P 500 Index ETF',
        'XIC': 'iShares Core S&P Total Canadian Stock Market ETF',
        'VAB': 'Vanguard Canadian Aggregate Bond Index ETF',
        'XBB': 'iShares Core Canadian Universe Bond Index ETF',
        'TDB902': 'TD Canadian Index Fund',
        'XQQ': 'iShares Core S&P 500 Hedged to CAD Index ETF',
        'VEE': 'Vanguard Emerging Markets Stock Index ETF'
    }


# Example usage and testing function
def demo_etf_analysis():
    """Demonstrate ETF analysis capabilities."""
    print("🚀 ETF Performance Analysis Demo")
    print("=" * 50)
    
    # Example: $10K invested in XGRO on Jan 1, 2020
    result = calculate_investment_performance(
        symbol='XGRO',
        investment_amount=10000,
        start_date='2020-01-01'
    )
    
    print(f"📊 {result['symbol']} Performance Analysis:")
    print(f"💰 Initial Investment: ${result['initial_investment']:,.2f}")
    print(f"📅 Investment Period: {result['start_date']} to {result['end_date']}")
    print(f"📈 Total Final Value: ${result['total_final_value']:,.2f}")
    print(f"💵 Total Return: ${result['total_return_dollars']:,.2f}")
    print(f"📊 Total Return %: {result['total_return_percent']:.2f}%")
    print(f"📈 Annualized Return: {result['annualized_return_percent']:.2f}%")
    print(f"💰 Dividend Income: ${result['dividend_income']:.2f}")
    
    return result


if __name__ == '__main__':
    # Run demo if script is executed directly
    demo_etf_analysis()
