"""
PostgreSQL Utilities for Airflow DAG
====================================

Direct PostgreSQL operations for ticker data enrichment without Django.
Handles connections, change detection, and data storage.
"""

import psycopg2
import psycopg2.extras
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PostgreSQLManager:
    """Direct PostgreSQL manager for enriched ticker data operations."""
    
    def __init__(self, host: str = 'db', port: int = 5432, 
                 database: str = 'stockdb', user: str = 'stockuser', 
                 password: str = 'stockpass'):
        """Initialize PostgreSQL connection parameters."""
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        logger.info(f"PostgreSQL Manager initialized for {database}@{host}")
    
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
        """Test the PostgreSQL connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    logger.info(f"✅ PostgreSQL connection test successful: {result}")
                    return True
        except Exception as e:
            logger.error(f"❌ PostgreSQL connection test failed: {e}")
            return False
    
    def get_all_tickers(self) -> List[str]:
        """Get all unique tickers from the listings table."""
        query = """
        SELECT DISTINCT symbol 
        FROM stocks_listing 
        WHERE symbol IS NOT NULL 
        AND LENGTH(symbol) BETWEEN 1 AND 32
        ORDER BY symbol
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    tickers = [row[0].upper() for row in cur.fetchall()]
                    logger.info(f"📊 Found {len(tickers)} unique tickers")
                    return tickers
        except Exception as e:
            logger.error(f"Error fetching tickers: {e}")
            return []
    
    def get_stale_tickers(self, days: int = 7) -> List[str]:
        """Get tickers that need refreshing (stale or missing data)."""
        query = """
        SELECT DISTINCT l.symbol
        FROM stocks_listing l
        LEFT JOIN enriched_ticker_data e ON UPPER(l.symbol) = UPPER(e.symbol)
        WHERE l.symbol IS NOT NULL
        AND (
            e.symbol IS NULL  -- No enriched data exists
            OR e.last_checked_at IS NULL  -- Never checked
            OR e.last_checked_at < NOW() - INTERVAL '%s days'  -- Stale data
            OR e.fetch_success = FALSE  -- Previous failure
        )
        ORDER BY l.symbol
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (days,))
                    stale_tickers = [row[0].upper() for row in cur.fetchall()]
                    logger.info(f"📅 Found {len(stale_tickers)} stale tickers")
                    return stale_tickers
        except Exception as e:
            logger.error(f"Error fetching stale tickers: {e}")
            return []
    
    def calculate_data_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of key data fields for change detection."""
        # Include all the fields that matter for change detection
        key_data = {
            'asset_type': data.get('asset_type', 'OTHER'),
            'sector': data.get('sector'),
            'industry': data.get('industry'),
            'country': data.get('country'),
            'region': data.get('region'),
            'market_cap': data.get('market_cap'),
            'currency': data.get('currency'),
            'is_active': data.get('is_active', True),
        }
        
        # Convert to sorted string representation for consistent hashing
        data_str = str(sorted(key_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def get_latest_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of data for a ticker."""
        query = """
        SELECT symbol, version, asset_type, sector, industry, country, region,
               market_cap, currency, is_active, data_hash, last_checked_at,
               data_changed_at, fetch_success
        FROM enriched_ticker_data
        WHERE UPPER(symbol) = UPPER(%s)
        ORDER BY version DESC
        LIMIT 1
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, (symbol,))
                    row = cur.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching latest data for {symbol}: {e}")
            return None
    
    def has_data_changed(self, symbol: str, new_data: Dict[str, Any]) -> bool:
        """Check if new data is different from the latest version."""
        latest = self.get_latest_ticker_data(symbol)
        if not latest:
            return True  # No existing data, so it's "changed"
        
        new_hash = self.calculate_data_hash(new_data)
        return latest['data_hash'] != new_hash
    
    def create_or_update_ticker_data(self, symbol: str, data: Dict[str, Any]) -> Tuple[bool, int]:
        """
        Create a new version if data has changed, or update timestamp if unchanged.
        
        Returns:
            (data_changed: bool, version: int)
        """
        symbol = symbol.upper()
        
        if not self.has_data_changed(symbol, data):
            # Data hasn't changed, just update the last_checked_at timestamp
            self._update_last_checked(symbol)
            latest = self.get_latest_ticker_data(symbol)
            return False, latest['version'] if latest else 1
        
        # Data has changed, create new version
        return self._create_new_version(symbol, data)
    
    def _update_last_checked(self, symbol: str):
        """Update the last_checked_at timestamp for existing record."""
        query = """
        UPDATE enriched_ticker_data 
        SET last_checked_at = NOW()
        WHERE UPPER(symbol) = UPPER(%s) 
        AND version = (
            SELECT MAX(version) 
            FROM enriched_ticker_data 
            WHERE UPPER(symbol) = UPPER(%s)
        )
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (symbol, symbol))
                    conn.commit()
                    logger.debug(f"🔄 Updated timestamp for {symbol}")
                    
        except Exception as e:
            logger.error(f"Error updating timestamp for {symbol}: {e}")
            raise
    
    def _create_new_version(self, symbol: str, data: Dict[str, Any]) -> Tuple[bool, int]:
        """Create a new version of ticker data."""
        latest = self.get_latest_ticker_data(symbol)
        new_version = (latest['version'] + 1) if latest else 1
        
        insert_query = """
        INSERT INTO enriched_ticker_data (
            symbol, version, company_name, exchange, asset_type, asset_confidence,
            sector, industry, sector_key, industry_key, country, country_code, region,
            market_cap, currency, is_active, data_source, data_quality_score,
            fetch_success, fetch_errors, data_hash, data_changed_at, first_loaded_at,
            last_updated_at, last_checked_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            NOW(), 
            CASE WHEN %s = 1 THEN NOW() ELSE (
                SELECT first_loaded_at FROM enriched_ticker_data 
                WHERE UPPER(symbol) = UPPER(%s) LIMIT 1
            ) END,
            NOW(), NOW()
        )
        """
        
        # Calculate data hash
        data_hash = self.calculate_data_hash(data)
        
        # Prepare insert values
        values = (
            symbol.upper(),                              # symbol
            new_version,                                 # version
            data.get('company_name'),                    # company_name
            data.get('exchange'),                        # exchange
            data.get('asset_type', 'OTHER'),             # asset_type
            data.get('asset_confidence', 0.0),           # asset_confidence
            data.get('sector'),                          # sector
            data.get('industry'),                        # industry
            data.get('sector_key'),                      # sector_key
            data.get('industry_key'),                    # industry_key
            data.get('country'),                         # country
            data.get('country_code'),                    # country_code
            data.get('region'),                          # region
            data.get('market_cap'),                      # market_cap
            data.get('currency'),                        # currency
            data.get('is_active', True),                 # is_active
            data.get('data_source', 'airflow_dag'),      # data_source
            data.get('data_quality_score', 0.0),         # data_quality_score
            data.get('fetch_success', True),             # fetch_success
            json.dumps(data.get('fetch_errors')),        # fetch_errors (JSON)
            data_hash,                                   # data_hash
            new_version,                                 # for first_loaded_at logic
            symbol.upper()                               # for first_loaded_at subquery
        )
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(insert_query, values)
                    conn.commit()
                    logger.info(f"✅ Created new version {new_version} for {symbol}")
                    return True, new_version
                    
        except Exception as e:
            logger.error(f"Error creating new version for {symbol}: {e}")
            raise
    
    def bulk_update_tickers(self, ticker_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Bulk update multiple tickers efficiently.
        
        Returns:
            Statistics dictionary with counts
        """
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0
        }
        
        for ticker_info in ticker_data:
            try:
                symbol = ticker_info['symbol']
                data_changed, version = self.create_or_update_ticker_data(symbol, ticker_info)
                
                if data_changed:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1
                
                stats['processed'] += 1
                
            except Exception as e:
                logger.error(f"Error processing {ticker_info.get('symbol', 'UNKNOWN')}: {e}")
                stats['errors'] += 1
        
        return stats
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get current enrichment statistics from the database."""
        stats_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT symbol) as unique_tickers,
            COUNT(CASE WHEN last_checked_at >= NOW() - INTERVAL '1 day' THEN 1 END) as fresh_tickers,
            COUNT(CASE WHEN last_checked_at < NOW() - INTERVAL '7 days' OR last_checked_at IS NULL THEN 1 END) as stale_tickers,
            AVG(data_quality_score) as avg_quality_score
        FROM enriched_ticker_data
        """
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(stats_query)
                    stats = dict(cur.fetchone())
                    
                    # Convert to more readable format
                    stats['avg_quality_score'] = round(float(stats['avg_quality_score'] or 0), 2)
                    stats['coverage_percentage'] = round(
                        (stats['fresh_tickers'] / stats['unique_tickers'] * 100) 
                        if stats['unique_tickers'] > 0 else 0, 1
                    )
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"Error getting enrichment stats: {e}")
            return {
                'total_records': 0,
                'unique_tickers': 0, 
                'fresh_tickers': 0,
                'stale_tickers': 0,
                'avg_quality_score': 0.0,
                'coverage_percentage': 0.0
            }


# Convenience functions for DAG usage
def get_db_manager() -> PostgreSQLManager:
    """Get configured PostgreSQL manager."""
    return PostgreSQLManager()


def test_database_connection() -> bool:
    """Test database connection - useful for DAG health checks."""
    manager = get_db_manager()
    return manager.test_connection()


def get_stale_tickers(days: int = 7) -> List[str]:
    """Get tickers needing refresh - main DAG entry point."""
    manager = get_db_manager()
    return manager.get_stale_tickers(days)
