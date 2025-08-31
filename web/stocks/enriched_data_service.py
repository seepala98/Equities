"""
Enriched Data Service
====================

Service layer for retrieving ticker data with database-first approach.
Falls back to yfinance API when database data is missing or stale.

This replaces direct API calls throughout the webapp with intelligent
database-first queries that are much faster and reduce API usage.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from .models import EnrichedTickerData
from .asset_classifier import AssetClassifier
from .sector_analysis_utils import SectorAnalyzer

logger = logging.getLogger(__name__)


class EnrichedDataService:
    """
    Service for retrieving enriched ticker data with database-first approach.
    """
    
    def __init__(self):
        self.asset_classifier = AssetClassifier()
        self.sector_analyzer = SectorAnalyzer()
    
    def get_ticker_info(self, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive ticker information.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL', 'SHOP.TO')
            force_refresh: If True, bypass database and force API call
            
        Returns:
            Dictionary with ticker information including source metadata
        """
        symbol = symbol.upper()
        
        if not force_refresh:
            # Step 1: Try to get fresh data from database
            db_data = self._get_from_database(symbol)
            if db_data:
                logger.info(f"🗄️ Using database data for {symbol}")
                return db_data
        
        # Step 2: Fallback to API enrichment
        logger.info(f"📡 Fetching fresh data for {symbol} via API")
        api_data = self._fetch_from_api(symbol)
        
        # Step 3: Store the API data for future use
        if api_data['success']:
            self._store_enriched_data(symbol, api_data)
        
        return api_data
    
    def get_tickers_by_asset_type(self, asset_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tickers filtered by asset type.
        
        Args:
            asset_type: Asset type filter ('STOCK', 'ETF', etc.)
            limit: Maximum number of results
            
        Returns:
            List of ticker information dictionaries
        """
        logger.info(f"🔍 Searching database for {asset_type} assets (limit: {limit})")
        
        # Get latest version of each ticker with the specified asset type
        tickers = EnrichedTickerData.objects.filter(
            asset_type=asset_type
        ).values('symbol').distinct()[:limit]
        
        results = []
        for ticker_data in tickers:
            latest_data = EnrichedTickerData.get_latest_version(ticker_data['symbol'])
            if latest_data:
                results.append(self._convert_to_api_format(latest_data))
        
        logger.info(f"📊 Found {len(results)} {asset_type} assets in database")
        return results
    
    def get_tickers_by_sector(self, sector: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tickers filtered by sector.
        
        Args:
            sector: Sector name (e.g., 'Technology', 'Healthcare')
            limit: Maximum number of results
            
        Returns:
            List of ticker information dictionaries
        """
        logger.info(f"🔍 Searching database for {sector} sector tickers (limit: {limit})")
        
        # Search for tickers in the specified sector
        tickers = EnrichedTickerData.objects.filter(
            Q(sector__icontains=sector) | Q(sector_key__icontains=sector.lower())
        ).values('symbol').distinct()[:limit]
        
        results = []
        for ticker_data in tickers:
            latest_data = EnrichedTickerData.get_latest_version(ticker_data['symbol'])
            if latest_data:
                results.append(self._convert_to_api_format(latest_data))
        
        logger.info(f"📊 Found {len(results)} {sector} sector tickers in database")
        return results
    
    def get_tickers_by_region(self, region: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tickers filtered by geographic region.
        
        Args:
            region: Region name (e.g., 'North America', 'Europe')
            limit: Maximum number of results
            
        Returns:
            List of ticker information dictionaries
        """
        logger.info(f"🌍 Searching database for {region} region tickers (limit: {limit})")
        
        tickers = EnrichedTickerData.objects.filter(
            Q(region__icontains=region) | Q(country__icontains=region)
        ).values('symbol').distinct()[:limit]
        
        results = []
        for ticker_data in tickers:
            latest_data = EnrichedTickerData.get_latest_version(ticker_data['symbol'])
            if latest_data:
                results.append(self._convert_to_api_format(latest_data))
        
        logger.info(f"📊 Found {len(results)} {region} region tickers in database")
        return results
    
    def search_tickers(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search tickers by symbol or company name.
        
        Args:
            query: Search term
            limit: Maximum number of results
            
        Returns:
            List of matching ticker information
        """
        logger.info(f"🔍 Searching database for tickers matching '{query}' (limit: {limit})")
        
        query_upper = query.upper()
        
        # Search by symbol or company name
        tickers = EnrichedTickerData.objects.filter(
            Q(symbol__icontains=query_upper) | 
            Q(company_name__icontains=query)
        ).values('symbol').distinct()[:limit]
        
        results = []
        for ticker_data in tickers:
            latest_data = EnrichedTickerData.get_latest_version(ticker_data['symbol'])
            if latest_data:
                results.append(self._convert_to_api_format(latest_data))
        
        # Sort by relevance (exact symbol matches first)
        results.sort(key=lambda x: (
            0 if x['symbol'].startswith(query_upper) else 1,
            x['symbol']
        ))
        
        logger.info(f"📊 Found {len(results)} tickers matching '{query}'")
        return results
    
    def get_data_freshness_stats(self) -> Dict[str, Any]:
        """
        Get statistics about data freshness in the database.
        
        Returns:
            Dictionary with freshness statistics
        """
        now = timezone.now()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)
        
        total_records = EnrichedTickerData.objects.count()
        unique_tickers = EnrichedTickerData.objects.values('symbol').distinct().count()
        
        fresh_records = EnrichedTickerData.objects.filter(
            last_checked_at__gte=one_day_ago
        ).values('symbol').distinct().count()
        
        stale_records = EnrichedTickerData.objects.filter(
            last_checked_at__lt=one_week_ago
        ).values('symbol').distinct().count()
        
        from django.db import models
        
        avg_quality_score = EnrichedTickerData.objects.aggregate(
            avg_quality=models.Avg('data_quality_score')
        )['avg_quality'] or 0.0
        
        stats = {
            'total_records': total_records,
            'unique_tickers': unique_tickers,
            'fresh_tickers': fresh_records,
            'stale_tickers': stale_records,
            'coverage_percentage': (fresh_records / unique_tickers * 100) if unique_tickers > 0 else 0,
            'average_quality_score': round(avg_quality_score, 2),
            'last_updated': now.isoformat()
        }
        
        return stats
    
    def _get_from_database(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get ticker data from database if fresh and available.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Ticker data dictionary if available, None otherwise
        """
        latest_data = EnrichedTickerData.get_latest_version(symbol)
        
        if not latest_data:
            logger.debug(f"No database data found for {symbol}")
            return None
        
        if latest_data.is_stale:
            logger.debug(f"Database data for {symbol} is stale")
            return None
        
        if not latest_data.fetch_success:
            logger.debug(f"Database data for {symbol} marked as failed")
            return None
        
        # Convert to API format
        return self._convert_to_api_format(latest_data)
    
    def _convert_to_api_format(self, enriched_data: EnrichedTickerData) -> Dict[str, Any]:
        """
        Convert EnrichedTickerData model to API response format.
        
        Args:
            enriched_data: EnrichedTickerData instance
            
        Returns:
            Dictionary in API response format
        """
        return {
            'symbol': enriched_data.symbol,
            'company_name': enriched_data.company_name,
            'exchange': enriched_data.exchange,
            
            # Asset classification
            'asset_type': enriched_data.asset_type,
            'asset_confidence': enriched_data.asset_confidence,
            
            # Sector information
            'sector': enriched_data.sector,
            'industry': enriched_data.industry,
            'sector_key': enriched_data.sector_key,
            'industry_key': enriched_data.industry_key,
            
            # Geographic information
            'country': enriched_data.country,
            'country_code': enriched_data.country_code,
            'region': enriched_data.region,
            
            # Market data
            'market_cap': enriched_data.market_cap,
            'currency': enriched_data.currency,
            'is_active': enriched_data.is_active,
            
            # Metadata
            'data_quality_score': enriched_data.data_completeness_score,
            'data_source': 'database',
            'cached_at': enriched_data.last_updated_at.isoformat(),
            'version': enriched_data.version,
            'success': enriched_data.fetch_success,
            'from_database': True
        }
    
    def _fetch_from_api(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch fresh data from APIs when database data is unavailable.
        
        Uses comprehensive yfinance enrichment for webapp fallback scenarios.
        This data will be stored in cache for future use.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Dictionary with enriched ticker data
        """
        logger.info(f"📡 Webapp API fallback: fetching comprehensive data for {symbol}")
        
        try:
            import yfinance as yf
            
            # Create yfinance ticker
            ticker = yf.Ticker(symbol)
            
            # Fetch comprehensive info
            try:
                info = ticker.info or {}
                logger.debug(f"✅ yfinance info fetched for {symbol}")
            except Exception as e:
                logger.warning(f"⚠️ yfinance info failed for {symbol}: {e}")
                info = {}
            
            # Extract comprehensive data using similar logic to background processing
            api_data = self._extract_comprehensive_api_data(symbol, info)
            
            # Fallback to sector analysis if yfinance fails
            if not api_data.get('success') or api_data.get('data_quality_score', 0) < 0.3:
                logger.info(f"🔄 yfinance quality low for {symbol}, trying sector analysis fallback")
                sector_data = self.sector_analyzer.enhance_stock_with_sector_data(symbol)
                
                # Merge sector data into api_data
                if sector_data.get('success'):
                    api_data.update({
                        'sector': sector_data.get('sector'),
                        'industry': sector_data.get('industry'),
                        'sector_key': sector_data.get('sector_key'),
                        'industry_key': sector_data.get('industry_key'),
                        'success': True
                    })
                    
                    # Recalculate quality score
                    filled_fields = sum(1 for field in [
                        api_data.get('company_name'),
                        api_data.get('asset_type') if api_data.get('asset_type') != 'OTHER' else None,
                        api_data.get('sector'),
                        api_data.get('industry'),
                        api_data.get('country'),
                        api_data.get('market_cap'),
                        api_data.get('currency'),
                        api_data.get('exchange')
                    ] if field)
                    
                    api_data['data_quality_score'] = min(filled_fields / 8, 1.0)
            
            logger.info(f"✅ Webapp API fallback complete for {symbol} (Quality: {api_data.get('data_quality_score', 0):.2f})")
            return api_data
            
        except Exception as e:
            logger.error(f"❌ Error in webapp API fallback for {symbol}: {e}")
            return {
                'symbol': symbol,
                'success': False,
                'error': str(e),
                'data_source': 'webapp_api_error',
                'from_database': False,
                'data_quality_score': 0.0
            }
    
    def _extract_comprehensive_api_data(self, symbol: str, info: Dict) -> Dict[str, Any]:
        """
        Extract comprehensive data from yfinance info dict.
        
        This mirrors the background processing logic for consistency.
        
        Args:
            symbol: Ticker symbol
            info: yfinance info dictionary
            
        Returns:
            Comprehensive ticker data dictionary
        """
        # Company data
        company_name = info.get('longName') or info.get('shortName')
        exchange = info.get('exchange')
        currency = info.get('currency', 'USD')
        
        # Advanced asset classification
        quote_type = info.get('quoteType', '').upper()
        long_name = (company_name or '').upper()
        
        asset_confidence = 0.5  # Default
        
        if quote_type == 'ETF' or 'ETF' in long_name:
            asset_type = 'ETF'
            asset_confidence = 0.95
        elif quote_type == 'MUTUALFUND':
            asset_type = 'MUTUAL_FUND'
            asset_confidence = 0.95
        elif quote_type == 'EQUITY' or quote_type == 'STOCK':
            if 'REIT' in long_name:
                asset_type = 'REIT'
                asset_confidence = 0.9
            elif 'PREFERRED' in long_name or '.PR' in symbol:
                asset_type = 'PREFERRED'
                asset_confidence = 0.9
            else:
                asset_type = 'STOCK'
                asset_confidence = 0.8
        elif symbol.endswith('.WT') or symbol.endswith('.W'):
            asset_type = 'WARRANT'
            asset_confidence = 0.85
        else:
            asset_type = 'OTHER'
            asset_confidence = 0.3
        
        # Sector and industry
        sector = info.get('sector')
        industry = info.get('industry')
        
        # Geographic data
        country = info.get('country')
        if not country:
            # Infer from symbol
            if symbol.endswith('.TO') or symbol.endswith('.V'):
                country = 'Canada'
            elif symbol.endswith('.L') or symbol.endswith('.LSE'):
                country = 'United Kingdom'
            elif symbol.endswith('.DE') or symbol.endswith('.F'):
                country = 'Germany'
            else:
                country = 'United States'
        
        # Country to region mapping
        region_mapping = {
            'Canada': ('North America', 'CA'),
            'United States': ('North America', 'US'),
            'United Kingdom': ('Europe', 'GB'),
            'Germany': ('Europe', 'DE'),
            'France': ('Europe', 'FR'),
            'Japan': ('Asia', 'JP'),
            'China': ('Asia', 'CN'),
            'Australia': ('Oceania', 'AU')
        }
        
        region, country_code = region_mapping.get(country, ('North America', 'US'))
        
        # Market cap
        market_cap = info.get('marketCap')
        if market_cap and isinstance(market_cap, (int, float)):
            market_cap = int(market_cap)
        else:
            market_cap = None
        
        # Calculate quality score
        filled_fields = sum(1 for field in [
            company_name,
            asset_type if asset_type != 'OTHER' else None,
            sector,
            industry,
            country,
            market_cap,
            currency,
            exchange
        ] if field)
        
        quality_score = min(filled_fields / 8, 1.0)
        
        return {
            'symbol': symbol,
            'company_name': company_name,
            'exchange': exchange,
            'asset_type': asset_type,
            'asset_confidence': asset_confidence,
            'sector': sector,
            'industry': industry,
            'sector_key': self._generate_key(sector),
            'industry_key': self._generate_key(industry),
            'country': country,
            'country_code': country_code,
            'region': region,
            'market_cap': market_cap,
            'currency': currency,
            'is_active': True,
            'data_quality_score': quality_score,
            'data_source': 'webapp_yfinance_fallback',
            'success': quality_score > 0.2,  # Success if we got some meaningful data
            'from_database': False
        }
    
    def _generate_key(self, name: Optional[str]) -> Optional[str]:
        """Generate a key for sector/industry from name."""
        if not name:
            return None
        import re
        return re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
    
    def _store_enriched_data(self, symbol: str, api_data: Dict[str, Any]) -> bool:
        """
        Store API-fetched data in the database for future use.
        
        Args:
            symbol: Ticker symbol
            api_data: Data fetched from API
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            if not api_data.get('success'):
                return False
            
            # Prepare data for storage
            storage_data = {
                'company_name': api_data.get('company_name'),
                'exchange': api_data.get('exchange'),
                'asset_type': api_data.get('asset_type', 'OTHER'),
                'asset_confidence': api_data.get('asset_confidence', 0.0),
                'sector': api_data.get('sector'),
                'industry': api_data.get('industry'),
                'sector_key': api_data.get('sector_key'),
                'industry_key': api_data.get('industry_key'),
                'country': api_data.get('country'),
                'country_code': api_data.get('country_code'),
                'region': api_data.get('region'),
                'market_cap': api_data.get('market_cap'),
                'currency': api_data.get('currency'),
                'is_active': api_data.get('is_active', True),
                'data_source': 'webapp_api_fallback',
                'data_quality_score': api_data.get('data_quality_score', 0.0),
                'fetch_success': True
            }
            
            # Store using the change detection logic
            record, created = EnrichedTickerData.create_new_version(symbol, storage_data)
            
            if created:
                logger.info(f"💾 Stored new enriched data for {symbol}")
            else:
                logger.debug(f"🔄 Updated timestamp for {symbol}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing enriched data for {symbol}: {e}")
            return False


# Convenience functions for backward compatibility
def get_ticker_info(symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Convenience function to get ticker info."""
    service = EnrichedDataService()
    return service.get_ticker_info(symbol, force_refresh)


def search_tickers(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Convenience function to search tickers."""
    service = EnrichedDataService()
    return service.search_tickers(query, limit)


def get_tickers_by_asset_type(asset_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Convenience function to get tickers by asset type."""
    service = EnrichedDataService()
    return service.get_tickers_by_asset_type(asset_type, limit)
