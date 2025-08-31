"""
Sector and Industry Analysis Integration
Uses yfinance's official Sector and Industry modules to enhance our existing system
"""
import yfinance as yf
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
import logging

# Django imports
from django.db import transaction
from .models import Listing, ETFInfo, Sector as SectorModel, YFinanceSectorCache, YFinanceStockSectorCache
from .etf_utils import calculate_investment_performance

logger = logging.getLogger(__name__)


class SectorAnalyzer:
    """Enhanced sector analysis using yfinance's official Sector/Industry modules."""
    
    # Available sector keys from yfinance
    SECTOR_KEYS = {
        'technology': 'Technology',
        'healthcare': 'Healthcare', 
        'financial-services': 'Financial Services',
        'consumer-cyclical': 'Consumer Cyclical',
        'communication-services': 'Communication Services',
        'industrials': 'Industrials',
        'consumer-defensive': 'Consumer Defensive',
        'energy': 'Energy',
        'basic-materials': 'Basic Materials',
        'real-estate': 'Real Estate',
        'utilities': 'Utilities',
    }
    
    def __init__(self):
        """Initialize the sector analyzer."""
        pass
    
    def get_sector_data(self, sector_key: str) -> Dict[str, Any]:
        """
        Get comprehensive sector data - first from cache, then from yfinance API if needed.
        
        Based on the official documentation:
        https://ranaroussi.github.io/yfinance/reference/yfinance.sector_industry.html
        """
        
        # Step 1: Check if we have fresh cached data
        cached_entry = YFinanceSectorCache.objects.filter(
            sector_key=sector_key,
            fetch_success=True
        ).first()
        
        if cached_entry and cached_entry.is_cache_fresh:
            logger.info(f"Using cached sector data for {sector_key}")
            return cached_entry.to_sector_data_dict()
        
        # Step 2: Cache miss or stale - fetch from yfinance API
        logger.info(f"Fetching fresh sector data for {sector_key} from yfinance API")
        
        try:
            # Initialize sector using yfinance
            sector = yf.Sector(sector_key)
            
            # Get basic sector information
            sector_data = {
                'key': sector.key,
                'name': sector.name,
                'symbol': getattr(sector, 'symbol', None),
                'overview': getattr(sector, 'overview', None),
                'success': True
            }
            
            # Get top companies in sector
            try:
                companies = sector.top_companies
                sector_data['top_companies'] = companies
                sector_data['has_top_companies'] = companies is not None and (not companies.empty if hasattr(companies, 'empty') else True)
            except Exception as e:
                logger.debug(f"Could not get top companies for {sector_key}: {e}")
                sector_data['top_companies'] = None
                sector_data['has_top_companies'] = False
            
            # Get top ETFs for this sector
            try:
                etfs = sector.top_etfs
                sector_data['top_etfs'] = etfs
                sector_data['has_top_etfs'] = etfs is not None and (not etfs.empty if hasattr(etfs, 'empty') else True)
            except Exception as e:
                logger.debug(f"Could not get top ETFs for {sector_key}: {e}")
                sector_data['top_etfs'] = None
                sector_data['has_top_etfs'] = False
            
            # Get top mutual funds
            try:
                funds = sector.top_mutual_funds
                sector_data['top_mutual_funds'] = funds
                sector_data['has_top_mutual_funds'] = funds is not None and (not funds.empty if hasattr(funds, 'empty') else True)
            except Exception as e:
                logger.debug(f"Could not get top mutual funds for {sector_key}: {e}")
                sector_data['top_mutual_funds'] = None
                sector_data['has_top_mutual_funds'] = False
            
            # Get industries within this sector
            try:
                industries = sector.industries
                sector_data['industries'] = industries
                sector_data['has_industries'] = industries is not None and len(industries) > 0 if industries else False
            except Exception as e:
                logger.debug(f"Could not get industries for {sector_key}: {e}")
                sector_data['industries'] = None
                sector_data['has_industries'] = False
            
            # Get research reports
            try:
                sector_data['research_reports'] = sector.research_reports
                sector_data['has_research_reports'] = sector_data['research_reports'] is not None
            except Exception as e:
                logger.debug(f"Could not get research reports for {sector_key}: {e}")
                sector_data['research_reports'] = None
                sector_data['has_research_reports'] = False
            
            # Step 3: Cache the results for future use
            self._cache_sector_data(sector_key, sector_data)
            
            return sector_data
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error fetching sector data for {sector_key}: {e}")
            
            # Cache the error to avoid repeated failed API calls
            error_data = {
                'key': sector_key,
                'name': self.SECTOR_KEYS.get(sector_key, sector_key.title()),
                'error': error_msg,
                'success': False
            }
            self._cache_sector_data(sector_key, error_data)
            
            return error_data
    
    def _cache_sector_data(self, sector_key: str, sector_data: Dict[str, Any]):
        """Helper method to cache sector data."""
        try:
            # Helper to safely convert data to JSON-serializable format
            def make_json_safe(data):
                if data is None:
                    return None
                
                # Handle pandas DataFrames
                if hasattr(data, 'to_dict'):
                    return data.to_dict('records')  # Convert DataFrame to list of dicts
                elif hasattr(data, '__dict__'):
                    return data.__dict__  # Convert objects to dict
                elif isinstance(data, (list, dict, str, int, float, bool)):
                    return data  # Already JSON-safe
                else:
                    return str(data)  # Convert everything else to string
            
            cache_data = {
                'sector_key': sector_key,
                'sector_name': sector_data.get('name', sector_key.title()),
                'symbol': sector_data.get('symbol'),
                'overview': sector_data.get('overview'),
                'has_top_etfs': sector_data.get('has_top_etfs', False),
                'has_top_companies': sector_data.get('has_top_companies', False),
                'has_top_mutual_funds': sector_data.get('has_top_mutual_funds', False),
                'has_industries': sector_data.get('has_industries', False),
                'has_research_reports': sector_data.get('has_research_reports', False),
                'top_etfs_data': make_json_safe(sector_data.get('top_etfs')),
                'top_companies_data': make_json_safe(sector_data.get('top_companies')),
                'top_mutual_funds_data': make_json_safe(sector_data.get('top_mutual_funds')),
                'industries_data': make_json_safe(sector_data.get('industries')),
                'research_reports_data': make_json_safe(sector_data.get('research_reports')),
                'fetch_success': sector_data.get('success', False),
                'fetch_error': sector_data.get('error'),
            }
            
            # Create or update cache entry
            YFinanceSectorCache.objects.update_or_create(
                sector_key=sector_key,
                defaults=cache_data
            )
            
            logger.info(f"Cached sector data for {sector_key}")
            
        except Exception as cache_error:
            logger.error(f"Error caching sector data for {sector_key}: {cache_error}")
            # Don't fail the whole operation if caching fails
    
    def get_industry_data(self, industry_key: str) -> Dict[str, Any]:
        """
        Get industry-specific data using yfinance Industry module.
        """
        try:
            # Initialize industry using yfinance  
            industry = yf.Industry(industry_key)
            
            industry_data = {
                'key': industry.key,
                'name': industry.name,
                'sector_key': getattr(industry, 'sector_key', None),
                'sector_name': getattr(industry, 'sector_name', None),
                'overview': getattr(industry, 'overview', None),
                'success': True
            }
            
            # Get top performing companies
            try:
                industry_data['top_performing_companies'] = industry.top_performing_companies
            except Exception as e:
                logger.debug(f"Could not get top performing companies for {industry_key}: {e}")
                industry_data['top_performing_companies'] = None
            
            # Get top growth companies
            try:
                industry_data['top_growth_companies'] = industry.top_growth_companies
            except Exception as e:
                logger.debug(f"Could not get top growth companies for {industry_key}: {e}")
                industry_data['top_growth_companies'] = None
            
            return industry_data
            
        except Exception as e:
            logger.error(f"Error fetching industry data for {industry_key}: {e}")
            return {
                'key': industry_key,
                'name': industry_key.replace('-', ' ').title(),
                'error': str(e),
                'success': False
            }
    
    def enhance_stock_with_sector_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get sector/industry information for a specific stock - first from cache, then yfinance API.
        
        Based on the chaining example from documentation:
        msft = yf.Ticker('MSFT')
        tech = yf.Sector(msft.info.get('sectorKey'))
        """
        symbol = symbol.upper()
        
        # Step 1: Check if we have fresh cached stock data
        cached_stock = YFinanceStockSectorCache.objects.filter(
            symbol=symbol,
            fetch_success=True
        ).first()
        
        if cached_stock and cached_stock.is_cache_fresh:
            logger.info(f"Using cached stock sector data for {symbol}")
            result = cached_stock.to_stock_analysis_dict()
            
            # Also get sector data if we have a sector_key
            if result.get('sector_key'):
                try:
                    sector_data = self.get_sector_data(result['sector_key'])
                    if sector_data['success']:
                        result['sector_data'] = sector_data
                except Exception as e:
                    logger.debug(f"Could not get sector data for {result['sector_key']}: {e}")
            
            return result
        
        # Step 2: Cache miss or stale - fetch from yfinance API
        logger.info(f"Fetching fresh stock sector data for {symbol} from yfinance API")
        
        try:
            # Get ticker info first
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            result = {
                'symbol': symbol,
                'sector_key': info.get('sectorKey'),
                'industry_key': info.get('industryKey'), 
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'success': True
            }
            
            # Get detailed sector data if sector key is available
            if result['sector_key']:
                sector_data = self.get_sector_data(result['sector_key'])
                result['sector_data'] = sector_data
            
            # Get detailed industry data if industry key is available  
            if result['industry_key']:
                industry_data = self.get_industry_data(result['industry_key'])
                result['industry_data'] = industry_data
            
            # Cache the stock data for future use
            self._cache_stock_data(symbol, result)
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error enhancing {symbol} with sector data: {e}")
            
            error_data = {
                'symbol': symbol,
                'error': error_msg,
                'success': False
            }
            self._cache_stock_data(symbol, error_data)
            
            return error_data
    
    def _cache_stock_data(self, symbol: str, stock_data: Dict[str, Any]):
        """Helper method to cache stock sector data."""
        try:
            cache_data = {
                'symbol': symbol.upper(),
                'sector': stock_data.get('sector'),
                'industry': stock_data.get('industry'),
                'sector_key': stock_data.get('sector_key'),
                'industry_key': stock_data.get('industry_key'),
                'fetch_success': stock_data.get('success', False),
                'fetch_error': stock_data.get('error'),
            }
            
            # Create or update cache entry
            YFinanceStockSectorCache.objects.update_or_create(
                symbol=symbol.upper(),
                defaults=cache_data
            )
            
            logger.info(f"Cached stock sector data for {symbol}")
            
        except Exception as cache_error:
            logger.error(f"Error caching stock data for {symbol}: {cache_error}")
            # Don't fail the whole operation if caching fails
    
    def get_sector_etf_recommendations(self, sector_key: str) -> Dict[str, Any]:
        """
        Get ETF recommendations for a specific sector, combining yfinance data with our database.
        """
        try:
            # Get sector data from yfinance
            sector_data = self.get_sector_data(sector_key)
            
            if not sector_data['success']:
                return sector_data
            
            result = {
                'sector_name': sector_data['name'],
                'sector_key': sector_key,
                'yfinance_top_etfs': sector_data.get('top_etfs'),
                'our_etfs': [],
                'performance_analysis': {},
                'success': True
            }
            
            # Find ETFs in our database that might be related to this sector
            our_etfs = ETFInfo.objects.filter(
                name__icontains=sector_data['name']
            ) or ETFInfo.objects.filter(
                category__icontains=sector_data['name']
            )
            
            # Add performance analysis for each ETF
            for etf in our_etfs:
                try:
                    # Calculate 1-year performance for each ETF
                    performance = calculate_investment_performance(
                        symbol=etf.symbol,
                        investment_amount=10000,
                        start_date='2023-01-01'
                    )
                    
                    result['our_etfs'].append({
                        'symbol': etf.symbol,
                        'name': etf.name,
                        'aum': etf.aum_formatted,
                        'mer': etf.mer_formatted,
                        'performance': performance
                    })
                    
                except Exception as perf_error:
                    logger.debug(f"Performance calculation failed for {etf.symbol}: {perf_error}")
                    result['our_etfs'].append({
                        'symbol': etf.symbol,
                        'name': etf.name,
                        'aum': etf.aum_formatted,
                        'mer': etf.mer_formatted,
                        'performance': None
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting sector ETF recommendations for {sector_key}: {e}")
            return {
                'sector_key': sector_key,
                'error': str(e),
                'success': False
            }
    
    def create_sector_dashboard(self) -> Dict[str, Any]:
        """
        Create a comprehensive sector dashboard using yfinance sector data.
        """
        dashboard = {
            'sectors': {},
            'summary': {
                'total_sectors': len(self.SECTOR_KEYS),
                'processed': 0,
                'errors': []
            },
            'success': True
        }
        
        for sector_key, sector_name in self.SECTOR_KEYS.items():
            try:
                sector_data = self.get_sector_data(sector_key)
                
                if sector_data['success']:
                    dashboard['sectors'][sector_key] = {
                        'name': sector_data['name'],
                        'has_top_etfs': sector_data.get('has_top_etfs', False),
                        'has_top_companies': sector_data.get('has_top_companies', False),
                        'has_industries': sector_data.get('has_industries', False),
                        'industries_count': len(sector_data.get('industries', [])) if sector_data.get('has_industries') else 0,
                        'data': sector_data
                    }
                    dashboard['summary']['processed'] += 1
                else:
                    dashboard['summary']['errors'].append(f"{sector_key}: {sector_data.get('error', 'Unknown error')}")
                    
            except Exception as e:
                error_msg = f"Error processing sector {sector_key}: {e}"
                dashboard['summary']['errors'].append(error_msg)
                logger.error(error_msg)
        
        return dashboard


def demo_sector_analysis():
    """Demo the sector analysis capabilities."""
    
    print("🏭 Sector Analysis Demo")
    print("=" * 50)
    
    analyzer = SectorAnalyzer()
    
    # Test 1: Get technology sector data
    print("🔬 Testing Technology Sector...")
    tech_data = analyzer.get_sector_data('technology')
    
    if tech_data['success']:
        print(f"✅ Sector: {tech_data['name']}")
        print(f"📊 Top ETFs available: {tech_data.get('has_top_etfs', False)}")
        print(f"🏢 Top Companies available: {tech_data.get('has_top_companies', False)}")
        print(f"🏭 Industries available: {tech_data.get('has_industries', False)}")
        
        if tech_data.get('has_top_etfs', False):
            print("\n📈 Top Technology ETFs:")
            try:
                etfs = tech_data['top_etfs']
                if hasattr(etfs, 'head'):
                    print(etfs.head())
                else:
                    print("ETF data available but format unclear")
            except Exception as e:
                print(f"Error displaying ETFs: {e}")
    else:
        print(f"❌ Error: {tech_data.get('error')}")
    
    # Test 2: Get stock sector info
    print(f"\n💼 Testing Stock Sector Enhancement...")
    try:
        # Test with a known tech stock
        stock_data = analyzer.enhance_stock_with_sector_data('AAPL')
        
        if stock_data['success']:
            print(f"✅ AAPL Sector Info:")
            print(f"   Sector: {stock_data.get('sector')}")
            print(f"   Industry: {stock_data.get('industry')}")
            print(f"   Sector Key: {stock_data.get('sector_key')}")
            print(f"   Industry Key: {stock_data.get('industry_key')}")
        else:
            print(f"❌ Error: {stock_data.get('error')}")
            
    except Exception as e:
        print(f"Error in stock test: {e}")
    
    # Test 3: Sector dashboard
    print(f"\n🎛️ Testing Sector Dashboard...")
    try:
        dashboard = analyzer.create_sector_dashboard()
        
        print(f"✅ Dashboard created with {dashboard['summary']['processed']} sectors")
        print(f"📊 Available sectors:")
        
        for sector_key, data in list(dashboard['sectors'].items())[:5]:
            print(f"   • {data['name']}: {data['industries_count']} industries")
        
        if dashboard['summary']['errors']:
            print(f"⚠️  Errors: {len(dashboard['summary']['errors'])}")
            
    except Exception as e:
        print(f"Error creating dashboard: {e}")
    
    return tech_data, dashboard


if __name__ == '__main__':
    demo_sector_analysis()
