"""
Comprehensive Ticker Enrichment System
=====================================

Full-featured background enrichment using yfinance for:
- Asset classification (advanced detection)
- Sector and industry analysis  
- Geographic region analysis
- Company fundamentals
- Market cap and currency
- Performance metrics

This system runs in Airflow background, populating cache tables
for lightning-fast webapp performance.
"""

import yfinance as yf
import psycopg2
import psycopg2.extras
import hashlib
import json
import logging
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import contextmanager
import requests_cache
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Browser impersonation to avoid rate limiting
try:
    from curl_cffi import requests as cf_requests
    BROWSER_SESSION = cf_requests.Session(impersonate="chrome")
    logger.info("✅ Browser impersonation enabled with curl_cffi")
except ImportError:
    BROWSER_SESSION = None
    logger.warning("⚠️ curl_cffi not available, using standard requests")

# Setup requests cache for yfinance
requests_cache.install_cache(
    cache_name='yfinance_cache',
    backend='memory',
    expire_after=3600  # 1 hour cache
)


class ComprehensiveEnrichmentManager:
    """Comprehensive ticker enrichment using yfinance and PostgreSQL."""
    
    def __init__(self, host: str = 'db', port: int = 5432, 
                 database: str = 'stockdb', user: str = 'stockuser', 
                 password: str = 'stockpass'):
        """Initialize enrichment manager."""
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        logger.info(f"Comprehensive Enrichment Manager initialized")
    
    @contextmanager
    def get_connection(self):
        """Context manager for PostgreSQL connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            conn.autocommit = False
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    logger.info(f"✅ Database connection successful: {result}")
                    return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def get_stale_tickers(self, days: int = 7, limit: int = 1000, min_quality: float = 0.8) -> List[str]:
        """Get tickers needing enrichment (skips high-quality tickers >= 80% AND excludes 404 failed tickers)."""
        query = """
        SELECT DISTINCT l.symbol
        FROM stocks_listing l
        LEFT JOIN enriched_ticker_data e ON UPPER(l.symbol) = UPPER(e.symbol)
        WHERE l.symbol IS NOT NULL
        AND LENGTH(l.symbol) BETWEEN 1 AND 32
        AND (
            e.symbol IS NULL  -- No enriched data
            OR e.last_checked_at < NOW() - INTERVAL '%s days'  -- Stale
            OR (e.fetch_success = FALSE AND NOT e.fetch_errors::text LIKE '%%404_NOT_FOUND%%')  -- Failed but not 404
            OR e.data_quality_score < %s  -- Below quality threshold
        )
        AND NOT EXISTS (
            SELECT 1 FROM enriched_ticker_data e2 
            WHERE UPPER(e2.symbol) = UPPER(l.symbol) 
            AND e2.data_quality_score >= %s  -- Skip high-quality tickers
            AND e2.last_checked_at >= NOW() - INTERVAL '1 days'  -- Recent high-quality data
        )
        AND NOT EXISTS (
            SELECT 1 FROM enriched_ticker_data e3
            WHERE UPPER(e3.symbol) = UPPER(l.symbol)
            AND e3.fetch_errors::text LIKE '%%404_NOT_FOUND%%'  -- Skip 404 failed tickers permanently
        )
        ORDER BY l.symbol
        LIMIT %s
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # First, count how many 404 failed tickers we're skipping
                    skip_count_query = """
                    SELECT COUNT(DISTINCT l.symbol) 
                    FROM stocks_listing l
                    INNER JOIN enriched_ticker_data e ON UPPER(l.symbol) = UPPER(e.symbol)
                    WHERE e.fetch_errors::text LIKE '%404_NOT_FOUND%'
                    """
                    cur.execute(skip_count_query)
                    skipped_404_count = cur.fetchone()[0]
                    
                    cur.execute(query, (days, min_quality, min_quality, limit))
                    stale_tickers = [row[0].upper() for row in cur.fetchall()]
                    logger.info(f"📅 Found {len(stale_tickers)} stale tickers")
                    if skipped_404_count > 0:
                        logger.info(f"🚫 Automatically skipping {skipped_404_count} tickers permanently failed with 404 Not Found")
                    return stale_tickers
        except Exception as e:
            logger.error(f"Error fetching stale tickers: {e}")
            return []
    
    def _format_ticker_for_yahoo(self, symbol: str) -> str:
        """Format ticker symbol with proper exchange suffix for Yahoo Finance."""
        # Get exchange info from database
        query = """
        SELECT exchange FROM stocks_listing 
        WHERE UPPER(symbol) = %s
        LIMIT 1
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (symbol.upper(),))
                    result = cur.fetchone()
                    
                    if result:
                        exchange = result[0].upper()
                        
                        # Add appropriate suffix based on Canadian exchanges
                        if exchange == 'TSX':
                            formatted = f"{symbol}.TO"
                            logger.debug(f"🇨🇦 TSX ticker: {symbol} → {formatted}")
                            return formatted
                        elif exchange == 'TSXV':
                            formatted = f"{symbol}.V"
                            logger.debug(f"🇨🇦 TSXV ticker: {symbol} → {formatted}")
                            return formatted
                        elif exchange == 'CSE':
                            formatted = f"{symbol}.CN"
                            logger.debug(f"🇨🇦 CSE ticker: {symbol} → {formatted}")
                            return formatted
                        elif exchange == 'CBOE':
                            # CBOE might be U.S. or international, try as-is first
                            logger.debug(f"🇺🇸 CBOE ticker: {symbol} (no suffix)")
                            return symbol
                        else:
                            logger.debug(f"❓ Unknown exchange {exchange}: {symbol} (no suffix)")
                            return symbol
                    else:
                        logger.warning(f"⚠️ Exchange not found for {symbol}, using as-is")
                        return symbol
                        
        except Exception as e:
            logger.warning(f"⚠️ Error getting exchange for {symbol}: {e}")
            return symbol

    def comprehensive_ticker_analysis(self, symbol: str) -> Dict[str, Any]:
        """Perform comprehensive analysis of a ticker using yfinance."""
        logger.info(f"🔍 Analyzing {symbol} comprehensively...")
        
        analysis_result = {
            'symbol': symbol.upper(),
            'fetch_success': False,
            'fetch_errors': [],
            'data_quality_score': 0.0,
            'data_source': 'yfinance_comprehensive',
            'analysis_timestamp': datetime.now()
        }
        
        try:
            # Format ticker with proper exchange suffix for Yahoo Finance
            yahoo_symbol = self._format_ticker_for_yahoo(symbol)
            
            # Create yfinance ticker object with browser impersonation
            if BROWSER_SESSION:
                ticker = yf.Ticker(yahoo_symbol, session=BROWSER_SESSION)
                logger.debug(f"🌐 Using browser session for {yahoo_symbol}")
            else:
                ticker = yf.Ticker(yahoo_symbol)
                logger.debug(f"🔗 Using standard session for {yahoo_symbol}")
            
            # Fetch basic info with rate limit handling
            info = {}
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    info = ticker.info or {}
                    
                    # Check for 404/invalid ticker indicators
                    is_404_or_delisted = False
                    
                    # Check 1: Only has trailingPegRatio with None value (common 404 response)
                    if len(info) == 1 and 'trailingPegRatio' in info and info['trailingPegRatio'] is None:
                        logger.warning(f"🚫 Invalid ticker detected: {symbol} (only trailingPegRatio=None)")
                        is_404_or_delisted = True
                    
                    # Check 2: No essential price/company data indicators
                    elif not any(key in info for key in ['regularMarketPrice', 'symbol', 'shortName', 'longName']):
                        logger.warning(f"🚫 No essential ticker data for {symbol} - likely invalid or delisted")
                        is_404_or_delisted = True
                    
                    # Check 3: Try historical data to confirm
                    if not is_404_or_delisted:
                        try:
                            test_quote = ticker.history(period='1d')
                            if test_quote.empty:
                                logger.warning(f"🚫 No historical data for {symbol} - confirming invalid/delisted ticker")
                                is_404_or_delisted = True
                        except Exception as quote_e:
                            error_msg = str(quote_e).lower()
                            if any(phrase in error_msg for phrase in ['delisted', 'no data found', 'possibly delisted']):
                                logger.warning(f"🚫 Delisted ticker confirmed: {symbol} - {quote_e}")
                                is_404_or_delisted = True
                    
                    if is_404_or_delisted:
                        analysis_result['fetch_errors'].append("404_NOT_FOUND")
                        analysis_result['fetch_success'] = False
                        analysis_result['is_404_failed'] = True
                        logger.warning(f"🚫 MARKING AS 404 FAILED: {symbol}")
                    elif info:
                        analysis_result['fetch_success'] = True
                        logger.debug(f"✅ Basic info fetched for {symbol}")
                    else:
                        # Truly empty info (rare case)
                        analysis_result['fetch_errors'].append("EMPTY_INFO_RETURNED")
                        analysis_result['fetch_success'] = False
                        
                    break  # Success or 404 detected - exit retry loop
                    
                except Exception as e:
                    error_str = str(e)
                    
                    # Handle 404 errors specifically - these are permanent failures
                    if "404" in error_str or "Not Found" in error_str or "HTTP Error 404" in error_str:
                        logger.warning(f"🚫 404 Error for {symbol} - ticker not found, marking as permanently failed")
                        analysis_result['fetch_errors'].append("404_NOT_FOUND")
                        analysis_result['fetch_success'] = False
                        analysis_result['is_404_failed'] = True
                        break  # Don't retry 404 errors
                    
                    elif "429" in error_str or "Too Many Requests" in error_str:
                        if attempt < max_retries - 1:
                            backoff_time = (2 ** attempt) * 10  # 10, 20, 40 seconds
                            logger.warning(f"⚠️ Rate limit hit for {symbol}, waiting {backoff_time}s (attempt {attempt + 1}/{max_retries})")
                            time.sleep(backoff_time)
                            continue
                        else:
                            logger.error(f"❌ Rate limit exceeded for {symbol} after {max_retries} attempts")
                            analysis_result['fetch_errors'].append("RATE_LIMIT_EXCEEDED")
                            analysis_result['fetch_success'] = False
                            break
                    else:
                        analysis_result['fetch_errors'].append(f"API_ERROR: {error_str}")
                        logger.warning(f"⚠️ Info fetch failed for {symbol}: {e}")
                        break
            
            # Extract comprehensive data
            analysis_result.update(self._extract_company_data(info))
            analysis_result.update(self._extract_asset_classification(info, symbol))
            analysis_result.update(self._extract_sector_industry(info))
            analysis_result.update(self._extract_geographic_data(info, symbol))
            analysis_result.update(self._extract_financial_metrics(info))
            
            # Calculate data quality score
            analysis_result['data_quality_score'] = self._calculate_quality_score(analysis_result)
            
            logger.info(f"✅ Comprehensive analysis complete for {symbol} (Quality: {analysis_result['data_quality_score']:.2f})")
            
        except Exception as e:
            analysis_result['fetch_errors'].append(f"Critical error: {str(e)}")
            logger.error(f"❌ Critical error analyzing {symbol}: {e}")
        
        return analysis_result
    
    def _extract_company_data(self, info: Dict) -> Dict[str, Any]:
        """Extract company name and basic data."""
        return {
            'company_name': info.get('longName') or info.get('shortName'),
            'website': info.get('website'),
            'exchange': info.get('exchange'),
            'currency': info.get('currency', 'USD'),
            'is_active': True  # Assume active if data exists
        }
    
    def _extract_asset_classification(self, info: Dict, symbol: str) -> Dict[str, Any]:
        """Advanced asset type classification."""
        quote_type = info.get('quoteType', '').upper()
        long_name = (info.get('longName', '') or '').upper()
        category = (info.get('category', '') or '').upper()
        
        # Advanced classification logic
        asset_confidence = 0.5  # Default confidence
        
        if quote_type == 'ETF' or 'ETF' in long_name:
            asset_type = 'ETF'
            asset_confidence = 0.95
        elif quote_type == 'MUTUALFUND' or 'MUTUAL FUND' in long_name:
            asset_type = 'MUTUAL_FUND'
            asset_confidence = 0.95
        elif quote_type == 'EQUITY' or quote_type == 'STOCK':
            # Further classify equity
            if 'REIT' in long_name or info.get('industry') == 'REIT':
                asset_type = 'REIT'
                asset_confidence = 0.9
            elif 'PREFERRED' in long_name or '.PR' in symbol:
                asset_type = 'PREFERRED'
                asset_confidence = 0.9
            else:
                asset_type = 'STOCK'
                asset_confidence = 0.8
        elif quote_type == 'CURRENCY':
            asset_type = 'CURRENCY'
            asset_confidence = 0.95
        elif quote_type == 'FUTURE':
            asset_type = 'FUTURE'
            asset_confidence = 0.95
        elif quote_type == 'OPTION':
            asset_type = 'OPTION'
            asset_confidence = 0.95
        elif symbol.endswith('.WT') or symbol.endswith('.W'):
            asset_type = 'WARRANT'
            asset_confidence = 0.85
        else:
            # Fallback classification by symbol patterns
            if symbol.endswith('.TO'):
                asset_type = 'STOCK'  # Canadian stock
                asset_confidence = 0.7
            else:
                asset_type = 'OTHER'
                asset_confidence = 0.3
        
        return {
            'asset_type': asset_type,
            'asset_confidence': asset_confidence
        }
    
    def _extract_sector_industry(self, info: Dict) -> Dict[str, Any]:
        """Extract sector and industry information."""
        return {
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'sector_key': self._generate_sector_key(info.get('sector')),
            'industry_key': self._generate_industry_key(info.get('industry'))
        }
    
    def _extract_geographic_data(self, info: Dict, symbol: str) -> Dict[str, Any]:
        """Extract geographic information."""
        country = info.get('country')
        
        # If no country in info, infer from symbol
        if not country:
            if symbol.endswith('.TO') or symbol.endswith('.V'):
                country = 'Canada'
            elif symbol.endswith('.L') or symbol.endswith('.LSE'):
                country = 'United Kingdom'
            elif symbol.endswith('.DE') or symbol.endswith('.F'):
                country = 'Germany'
            else:
                country = 'United States'  # Default assumption
        
        # Map country to region
        country_to_region = {
            'Canada': 'North America',
            'United States': 'North America',
            'United Kingdom': 'Europe',
            'Germany': 'Europe',
            'France': 'Europe',
            'Italy': 'Europe',
            'Spain': 'Europe',
            'Japan': 'Asia',
            'China': 'Asia',
            'Australia': 'Oceania'
        }
        
        # Get country code
        country_codes = {
            'Canada': 'CA',
            'United States': 'US',
            'United Kingdom': 'GB',
            'Germany': 'DE',
            'France': 'FR',
            'Japan': 'JP',
            'China': 'CN',
            'Australia': 'AU'
        }
        
        return {
            'country': country,
            'country_code': country_codes.get(country, 'US'),
            'region': country_to_region.get(country, 'North America')
        }
    
    def _extract_financial_metrics(self, info: Dict) -> Dict[str, Any]:
        """Extract financial metrics."""
        market_cap = info.get('marketCap')
        
        # Handle market cap
        if market_cap and isinstance(market_cap, (int, float)):
            market_cap = int(market_cap)
        else:
            market_cap = None
        
        return {
            'market_cap': market_cap
        }
    
    def _generate_sector_key(self, sector: Optional[str]) -> Optional[str]:
        """Generate a sector key for database relationships."""
        if not sector:
            return None
        return re.sub(r'[^a-zA-Z0-9]', '_', sector.lower())
    
    def _generate_industry_key(self, industry: Optional[str]) -> Optional[str]:
        """Generate an industry key for database relationships."""
        if not industry:
            return None
        return re.sub(r'[^a-zA-Z0-9]', '_', industry.lower())
    
    def _calculate_quality_score(self, analysis_result: Dict[str, Any]) -> float:
        """Calculate data quality score (0-1)."""
        score = 0.0
        max_score = 10.0
        
        # Basic data presence
        if analysis_result.get('company_name'): score += 1.0
        if analysis_result.get('asset_type') and analysis_result.get('asset_type') != 'OTHER': score += 2.0
        if analysis_result.get('sector'): score += 1.5
        if analysis_result.get('industry'): score += 1.5
        if analysis_result.get('country'): score += 1.0
        if analysis_result.get('market_cap'): score += 1.0
        if analysis_result.get('currency'): score += 0.5
        if analysis_result.get('exchange'): score += 0.5
        
        # Bonus for high confidence asset classification
        if analysis_result.get('asset_confidence', 0) > 0.8: score += 1.0
        
        return min(score / max_score, 1.0)
    
    def update_enriched_data(self, symbol: str, analysis_data: Dict[str, Any]) -> bool:
        """Update enriched ticker data with change detection."""
        
        # Create data hash for change detection
        key_data = {
            'asset_type': analysis_data.get('asset_type'),
            'sector': analysis_data.get('sector'),
            'industry': analysis_data.get('industry'),
            'country': analysis_data.get('country'),
            'market_cap': analysis_data.get('market_cap'),
            'company_name': analysis_data.get('company_name')
        }
        data_hash = hashlib.sha256(str(sorted(key_data.items())).encode()).hexdigest()
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check for existing data
                    check_query = """
                    SELECT data_hash, version FROM enriched_ticker_data 
                    WHERE UPPER(symbol) = UPPER(%s) 
                    ORDER BY version DESC LIMIT 1
                    """
                    cur.execute(check_query, (symbol,))
                    existing = cur.fetchone()
                    
                    if existing and existing[0] == data_hash:
                        # Data unchanged, just update timestamp
                        update_query = """
                        UPDATE enriched_ticker_data 
                        SET last_checked_at = NOW()
                        WHERE UPPER(symbol) = UPPER(%s) 
                        AND version = %s
                        """
                        cur.execute(update_query, (symbol, existing[1]))
                        conn.commit()
                        logger.debug(f"🔄 Updated timestamp for {symbol}")
                        return True
                    
                    # Data changed or new - create new version
                    version_query = """
                    SELECT COALESCE(MAX(version), 0) + 1 
                    FROM enriched_ticker_data 
                    WHERE UPPER(symbol) = UPPER(%s)
                    """
                    cur.execute(version_query, (symbol,))
                    new_version = cur.fetchone()[0]
                    
                    # Insert comprehensive enriched data
                    insert_query = """
                    INSERT INTO enriched_ticker_data (
                        symbol, version, exchange, company_name, asset_type, asset_confidence,
                        sector, industry, sector_key, industry_key,
                        country, country_code, region, market_cap, currency,
                        is_active, data_source, data_quality_score, fetch_success,
                        fetch_errors, first_loaded_at, last_updated_at, last_checked_at,
                        data_changed_at, data_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        CASE WHEN %s = 1 THEN NOW() ELSE (
                            SELECT first_loaded_at FROM enriched_ticker_data 
                            WHERE UPPER(symbol) = UPPER(%s) LIMIT 1
                        ) END,
                        NOW(), NOW(), NOW(), %s
                    )
                    """
                    
                    cur.execute(insert_query, (
                        symbol.upper(), new_version,
                        analysis_data.get('exchange'), analysis_data.get('company_name'),
                        analysis_data.get('asset_type', 'OTHER'), analysis_data.get('asset_confidence', 0.0),
                        analysis_data.get('sector'), analysis_data.get('industry'),
                        analysis_data.get('sector_key'), analysis_data.get('industry_key'),
                        analysis_data.get('country'), analysis_data.get('country_code'),
                        analysis_data.get('region'), analysis_data.get('market_cap'),
                        analysis_data.get('currency'), analysis_data.get('is_active', True),
                        analysis_data.get('data_source', 'yfinance_comprehensive'),
                        analysis_data.get('data_quality_score', 0.0),
                        analysis_data.get('fetch_success', False),
                        json.dumps(analysis_data.get('fetch_errors', [])) if analysis_data.get('fetch_errors') else None,
                        new_version, symbol, data_hash
                    ))
                    
                    conn.commit()
                    
                    # Log 404 permanent failures prominently
                    if analysis_data.get('is_404_failed', False):
                        logger.warning(f"🚫 PERMANENTLY BLACKLISTED: {symbol} - 404 Not Found (will skip in future runs)")
                    else:
                        logger.info(f"✅ Updated {symbol} with version {new_version} (Quality: {analysis_data.get('data_quality_score', 0):.2f})")
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Error updating enriched data for {symbol}: {e}")
            return False
    
    def process_ticker_batch(self, tickers: List[str], batch_size: int = 50) -> Dict[str, int]:
        """Process a batch of tickers with comprehensive enrichment."""
        stats = {'processed': 0, 'updated': 0, 'errors': 0, 'high_quality': 0}
        
        logger.info(f"🔄 Processing batch of {len(tickers)} tickers...")
        
        for i, symbol in enumerate(tickers):
            try:
                logger.info(f"[{i+1}/{len(tickers)}] Processing {symbol}...")
                
                # Comprehensive analysis
                analysis_data = self.comprehensive_ticker_analysis(symbol)
                
                # Update database
                success = self.update_enriched_data(symbol, analysis_data)
                
                if success:
                    stats['updated'] += 1
                    if analysis_data.get('data_quality_score', 0) >= 0.8:
                        stats['high_quality'] += 1
                else:
                    stats['errors'] += 1
                
                stats['processed'] += 1
                
                # Respectful pause to avoid rate limiting  
                time.sleep(1.0)  # Increased from 0.1s to 1s to avoid 429 errors
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                stats['errors'] += 1
                stats['processed'] += 1
        
        logger.info(f"✅ Batch processing complete - Processed: {stats['processed']}, Updated: {stats['updated']}, High Quality: {stats['high_quality']}, Errors: {stats['errors']}")
        return stats
    
    def get_enrichment_statistics(self) -> Dict[str, Any]:
        """Get comprehensive enrichment statistics."""
        stats_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as unique_tickers,
            COUNT(CASE WHEN last_checked_at >= NOW() - INTERVAL '1 day' THEN 1 END) as fresh_today,
            COUNT(CASE WHEN last_checked_at >= NOW() - INTERVAL '7 days' THEN 1 END) as fresh_week,
            COUNT(CASE WHEN fetch_success = true THEN 1 END) as successful_fetches,
            COUNT(CASE WHEN data_quality_score >= 0.8 THEN 1 END) as high_quality,
            COUNT(CASE WHEN data_quality_score >= 0.6 THEN 1 END) as medium_quality,
            AVG(data_quality_score) as avg_quality_score,
            COUNT(CASE WHEN asset_type = 'STOCK' THEN 1 END) as stocks,
            COUNT(CASE WHEN asset_type = 'ETF' THEN 1 END) as etfs,
            COUNT(CASE WHEN asset_type = 'MUTUAL_FUND' THEN 1 END) as mutual_funds,
            COUNT(CASE WHEN sector IS NOT NULL THEN 1 END) as has_sector_data,
            COUNT(CASE WHEN market_cap IS NOT NULL THEN 1 END) as has_market_cap
        FROM enriched_ticker_data
        WHERE version = (
            SELECT MAX(version) FROM enriched_ticker_data e2 
            WHERE e2.symbol = enriched_ticker_data.symbol
        )
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(stats_query)
                    stats = dict(cur.fetchone())
                    
                    # Calculate percentages
                    total = stats['unique_tickers'] or 1
                    stats.update({
                        'fresh_today_pct': round(stats['fresh_today'] / total * 100, 1),
                        'fresh_week_pct': round(stats['fresh_week'] / total * 100, 1),
                        'success_rate_pct': round(stats['successful_fetches'] / total * 100, 1),
                        'high_quality_pct': round(stats['high_quality'] / total * 100, 1),
                        'avg_quality_score': round(float(stats['avg_quality_score'] or 0), 3),
                        'sector_coverage_pct': round(stats['has_sector_data'] / total * 100, 1),
                        'market_cap_coverage_pct': round(stats['has_market_cap'] / total * 100, 1)
                    })
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"Error getting enrichment statistics: {e}")
            return {}


# Convenience functions for DAG usage
def get_enrichment_manager() -> ComprehensiveEnrichmentManager:
    """Get configured enrichment manager."""
    return ComprehensiveEnrichmentManager()


def test_comprehensive_connection() -> bool:
    """Test database connection."""
    manager = get_enrichment_manager()
    return manager.test_connection()


def process_comprehensive_batch(batch_size: int = 50) -> Dict[str, Any]:
    """Process a comprehensive batch of tickers."""
    manager = get_enrichment_manager()
    
    # Get stale tickers (skip high-quality ones >= 80%)
    stale_tickers = manager.get_stale_tickers(days=7, limit=batch_size, min_quality=0.8)
    
    if not stale_tickers:
        return {'processed': 0, 'updated': 0, 'errors': 0, 'message': 'No stale tickers found'}
    
    # Process with comprehensive enrichment
    stats = manager.process_ticker_batch(stale_tickers, batch_size)
    return stats
