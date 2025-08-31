"""
ETF Holdings Data Collection Utilities
Fetches ETF holdings, sector allocations, and geographic data
"""
import yfinance as yf
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

# Django imports
from django.db import transaction
from .models import (
    ETFInfo, ETFHolding, ETFSectorAllocation, ETFGeographicAllocation,
    Sector, GeographicRegion, Listing, StockDetail
)

logger = logging.getLogger(__name__)


def get_or_create_sector(sector_name: str, sector_code: str = None) -> Sector:
    """Get or create a sector record."""
    sector, created = Sector.objects.get_or_create(
        sector_name=sector_name,
        defaults={
            'sector_code': sector_code,
            'description': f'{sector_name} sector'
        }
    )
    return sector


def get_or_create_region(region_name: str, country_name: str = None, 
                        country_code: str = None, region_type: str = None) -> GeographicRegion:
    """Get or create a geographic region record."""
    region, created = GeographicRegion.objects.get_or_create(
        region_name=region_name,
        country_name=country_name,
        defaults={
            'country_code': country_code,
            'region_type': region_type or 'Developed'
        }
    )
    return region


def populate_initial_sectors_and_regions():
    """Populate database with common sectors and regions."""
    # Common sectors
    sectors_data = [
        ('Technology', '45', 'Information Technology'),
        ('Healthcare', '35', 'Healthcare Equipment & Services, Pharmaceuticals'),
        ('Financials', '40', 'Banks, Insurance, Capital Markets'),
        ('Consumer Discretionary', '25', 'Automobiles, Retail, Media'),
        ('Communication Services', '50', 'Telecommunications, Media & Entertainment'),
        ('Industrials', '20', 'Aerospace, Defense, Transportation'),
        ('Consumer Staples', '30', 'Food, Beverage, Household Products'),
        ('Energy', '10', 'Oil, Gas, Renewable Energy'),
        ('Materials', '15', 'Chemicals, Construction Materials, Metals'),
        ('Real Estate', '60', 'REITs, Real Estate Management'),
        ('Utilities', '55', 'Electric, Gas, Water Utilities'),
    ]
    
    for sector_name, sector_code, description in sectors_data:
        sector, created = Sector.objects.get_or_create(
            sector_name=sector_name,
            defaults={
                'sector_code': sector_code,
                'description': description
            }
        )
        if created:
            print(f"Created sector: {sector_name}")
    
    # Common regions
    regions_data = [
        ('North America', 'United States', 'US', 'Developed'),
        ('North America', 'Canada', 'CA', 'Developed'),
        ('Europe', 'United Kingdom', 'GB', 'Developed'),
        ('Europe', 'Germany', 'DE', 'Developed'),
        ('Europe', 'France', 'FR', 'Developed'),
        ('Asia Pacific', 'Japan', 'JP', 'Developed'),
        ('Asia Pacific', 'Australia', 'AU', 'Developed'),
        ('Emerging Markets', 'China', 'CN', 'Emerging'),
        ('Emerging Markets', 'India', 'IN', 'Emerging'),
        ('Emerging Markets', 'Brazil', 'BR', 'Emerging'),
        ('Emerging Markets', 'South Korea', 'KR', 'Emerging'),
    ]
    
    for region_name, country_name, country_code, region_type in regions_data:
        # Use both region_name AND country_name for uniqueness
        region, created = GeographicRegion.objects.get_or_create(
            region_name=region_name,
            country_name=country_name,
            defaults={
                'country_code': country_code,
                'region_type': region_type
            }
        )
        if created:
            print(f"Created region: {region_name} - {country_name}")


def fetch_etf_basic_info(symbol: str) -> Dict:
    """Fetch basic ETF information from yfinance."""
    ticker_symbol = symbol.upper()
    if not ticker_symbol.endswith('.TO'):
        ticker_symbol += '.TO'
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        return {
            'symbol': symbol.upper(),
            'name': info.get('longName', f'ETF {symbol}'),
            'fund_family': info.get('family', ''),
            'category': info.get('category', ''),
            'currency': info.get('currency', 'CAD'),
            'assets_under_management': info.get('totalAssets', 0),
            'expense_ratio': info.get('annualHoldingsTurnover', 0) / 10000 if info.get('annualHoldingsTurnover') else None,  # Convert to decimal
            'benchmark_index': info.get('fundBenchmark', ''),
            'investment_strategy': info.get('longBusinessSummary', ''),
        }
    
    except Exception as e:
        logger.error(f"Error fetching basic info for {symbol}: {e}")
        return {
            'symbol': symbol.upper(),
            'name': f'ETF {symbol}',
            'currency': 'CAD'
        }


def fetch_etf_holdings_yfinance(symbol: str) -> Tuple[Dict, List]:
    """
    Fetch ETF holdings using yfinance.
    Returns: (basic_info, holdings_list)
    """
    ticker_symbol = symbol.upper()
    if not ticker_symbol.endswith('.TO'):
        ticker_symbol += '.TO'
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Get basic info
        basic_info = fetch_etf_basic_info(symbol)
        
        # Try to get holdings (not available for all ETFs)
        holdings = []
        try:
            # This method may not exist for all ETFs
            holdings_data = ticker.get_holdings()
            
            if holdings_data is not None and not holdings_data.empty:
                for idx, row in holdings_data.iterrows():
                    holding = {
                        'symbol': str(row.get('Symbol', '')).strip(),
                        'name': str(row.get('Name', '')).strip(),
                        'weight': float(row.get('Weight', 0)) if row.get('Weight') else 0,
                        'shares': int(row.get('Shares', 0)) if row.get('Shares') else None,
                        'market_value': float(row.get('Market Value', 0)) if row.get('Market Value') else None,
                    }
                    
                    if holding['symbol'] and holding['weight'] > 0:
                        holdings.append(holding)
                        
        except Exception as holdings_error:
            logger.warning(f"Could not fetch holdings for {symbol}: {holdings_error}")
            
        return basic_info, holdings
        
    except Exception as e:
        logger.error(f"Error fetching holdings for {symbol}: {e}")
        return {'symbol': symbol, 'name': f'ETF {symbol}'}, []


def store_etf_holdings_data(symbol: str, basic_info: Dict, holdings: List) -> ETFInfo:
    """Store ETF information and holdings in the database."""
    
    with transaction.atomic():
        # Create or update ETF info
        etf_info, created = ETFInfo.objects.update_or_create(
            symbol=symbol.upper(),
            defaults=basic_info
        )
        
        if created:
            logger.info(f"Created new ETF: {symbol}")
        else:
            logger.info(f"Updated ETF: {symbol}")
        
        # Store holdings if available
        if holdings:
            # Delete existing holdings for today (in case of re-runs)
            today = date.today()
            ETFHolding.objects.filter(etf=etf_info, as_of_date=today).delete()
            
            holdings_created = 0
            for holding in holdings:
                # Try to find the stock in our listings
                stock_listing = None
                
                # First try exact match
                stock_listing = Listing.objects.filter(symbol=holding['symbol']).first()
                
                # If not found, try to create a basic listing entry
                if not stock_listing and holding['symbol']:
                    try:
                        stock_listing = Listing.objects.create(
                            exchange='OTHER',  # We'll need to determine exchange later
                            symbol=holding['symbol'],
                            name=holding['name'] or f"Stock {holding['symbol']}",
                            status='listed',
                            active=True
                        )
                        logger.info(f"Created new stock listing: {holding['symbol']}")
                    except Exception as e:
                        logger.warning(f"Could not create listing for {holding['symbol']}: {e}")
                        continue
                
                # Create holding record
                if stock_listing:
                    ETFHolding.objects.create(
                        etf=etf_info,
                        stock_listing=stock_listing,
                        weight_percentage=Decimal(str(holding['weight'])),
                        shares_held=holding.get('shares'),
                        market_value=holding.get('market_value'),
                        as_of_date=today,
                        data_source='yfinance'
                    )
                    holdings_created += 1
            
            logger.info(f"Stored {holdings_created} holdings for {symbol}")
        
        return etf_info


def fetch_and_store_etf(symbol: str) -> Dict:
    """Complete pipeline to fetch and store ETF data."""
    try:
        logger.info(f"Fetching ETF data for {symbol}...")
        
        # Fetch data from yfinance
        basic_info, holdings = fetch_etf_holdings_yfinance(symbol)
        
        # Store in database
        etf_info = store_etf_holdings_data(symbol, basic_info, holdings)
        
        result = {
            'success': True,
            'symbol': symbol,
            'etf_name': etf_info.name,
            'holdings_count': len(holdings),
            'message': f'Successfully processed {symbol} with {len(holdings)} holdings'
        }
        
        logger.info(result['message'])
        return result
        
    except Exception as e:
        error_msg = f"Error processing ETF {symbol}: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'symbol': symbol,
            'error': str(e),
            'message': error_msg
        }


def get_etf_holdings_summary(symbol: str) -> Dict:
    """Get a comprehensive summary of ETF holdings from database."""
    try:
        etf_info = ETFInfo.objects.get(symbol=symbol.upper())
        
        # Get holdings with stock details
        holdings = ETFHolding.objects.filter(etf=etf_info).select_related(
            'stock_listing', 'stock_listing__detail', 'stock_listing__detail__sector'
        ).order_by('-weight_percentage')[:20]  # Top 20 holdings
        
        holdings_data = []
        for holding in holdings:
            stock_data = {
                'symbol': holding.stock_listing.symbol,
                'name': holding.stock_listing.name,
                'weight_percentage': float(holding.weight_percentage),
                'exchange': holding.stock_listing.exchange,
                'sector': None,
                'region': None
            }
            
            # Add sector/region info if available
            if hasattr(holding.stock_listing, 'detail') and holding.stock_listing.detail:
                detail = holding.stock_listing.detail
                if detail.sector:
                    stock_data['sector'] = detail.sector.sector_name
                if detail.region:
                    stock_data['region'] = f"{detail.region.region_name} - {detail.region.country_name}"
            
            holdings_data.append(stock_data)
        
        # Get sector allocations
        sector_allocations = ETFSectorAllocation.objects.filter(etf=etf_info).select_related('sector')
        sector_data = [
            {
                'sector': alloc.sector.sector_name,
                'percentage': float(alloc.allocation_percentage)
            }
            for alloc in sector_allocations
        ]
        
        # Get geographic allocations
        geo_allocations = ETFGeographicAllocation.objects.filter(etf=etf_info).select_related('region')
        geo_data = [
            {
                'region': f"{alloc.region.region_name} - {alloc.region.country_name}",
                'percentage': float(alloc.allocation_percentage)
            }
            for alloc in geo_allocations
        ]
        
        return {
            'success': True,
            'etf_info': {
                'symbol': etf_info.symbol,
                'name': etf_info.name,
                'fund_family': etf_info.fund_family,
                'aum': etf_info.aum_formatted,
                'mer': etf_info.mer_formatted,
                'category': etf_info.category
            },
            'holdings': holdings_data,
            'sector_allocations': sector_data,
            'geographic_allocations': geo_data,
            'total_holdings': holdings.count()
        }
        
    except ETFInfo.DoesNotExist:
        return {
            'success': False,
            'error': f'ETF {symbol} not found in database. Please fetch it first.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error retrieving data for {symbol}: {e}'
        }


# Convenient function for testing
def demo_etf_holdings():
    """Demo function to test ETF holdings functionality."""
    print("🔍 ETF Holdings Analysis Demo")
    print("=" * 50)
    
    # Initialize sectors and regions
    print("📊 Setting up sectors and regions...")
    populate_initial_sectors_and_regions()
    
    # Test with XGRO
    print("\n🚀 Fetching XGRO holdings...")
    result = fetch_and_store_etf('XGRO')
    print(f"Result: {result}")
    
    if result['success']:
        print("\n📈 Getting holdings summary...")
        summary = get_etf_holdings_summary('XGRO')
        
        if summary['success']:
            etf_info = summary['etf_info']
            print(f"\n📋 {etf_info['symbol']} - {etf_info['name']}")
            print(f"💰 AUM: {etf_info['aum']} | MER: {etf_info['mer']}")
            print(f"📁 Category: {etf_info['category']}")
            
            print(f"\n🔝 Top Holdings ({len(summary['holdings'])}):")
            for i, holding in enumerate(summary['holdings'][:10], 1):
                print(f"{i:2}. {holding['symbol']:8} {holding['weight_percentage']:5.2f}% - {holding['name'][:40]}")
        
        return summary
    
    return result


if __name__ == '__main__':
    # Run demo if script is executed directly
    demo_etf_holdings()
