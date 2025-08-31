"""
Asset Classification System
Automatically classify stocks_listing entries into asset classes
"""
import re
import yfinance as yf
from typing import Dict, Optional, List, Tuple
from django.db import models, transaction
from .models import Listing
import logging

logger = logging.getLogger(__name__)


class AssetClassifier:
    """Main classifier for determining asset types from stock listings."""
    
    # Asset type choices that we'll add to the Listing model
    ASSET_TYPES = [
        ('STOCK', 'Individual Stock'),
        ('ETF', 'Exchange Traded Fund'),
        ('MUTUAL_FUND', 'Mutual Fund'),
        ('REIT', 'Real Estate Investment Trust'),
        ('TRUST', 'Business/Income Trust'),
        ('BOND', 'Bond/Fixed Income'),
        ('WARRANT', 'Warrant'),
        ('RIGHTS', 'Rights'),
        ('PREFERRED', 'Preferred Share'),
        ('UNIT', 'Unit/Hybrid Security'),
        ('CRYPTO', 'Cryptocurrency Product'),
        ('COMMODITY', 'Commodity Fund'),
        ('OTHER', 'Other/Unknown'),
    ]
    
    def __init__(self):
        """Initialize classification rules."""
        self.etf_patterns = [
            r'\bETF\b',  # Contains "ETF" as whole word
            r'\bExchange.Traded.Fund\b',
            r'\bIndex.Fund\b',
            r'\bTRACKED\b',
        ]
        
        self.reit_patterns = [
            r'\bREIT\b',
            r'Real Estate Investment Trust',
            r'Real Estate Income Trust',
            r'Property Trust',
        ]
        
        self.trust_patterns = [
            r'\bTRUST\b',
            r'Income Trust', 
            r'Business Trust',
            r'Royalty Trust',
        ]
        
        self.fund_patterns = [
            r'\bFUND\b',
            r'Investment Fund',
            r'Mutual Fund',
            r'Pooled Fund',
        ]
        
        self.bond_patterns = [
            r'\bBOND\b',
            r'\bDEBENTURE\b',
            r'Fixed Income',
            r'Government Bond',
            r'Corporate Bond',
        ]
        
        self.warrant_patterns = [
            r'\bWARRANT\b',
            r'\.WT\b',
            r'\.WS\b',
        ]
        
        self.rights_patterns = [
            r'\bRIGHTS?\b',
            r'\.RT\b',
            r'\.R\b',
        ]
        
        self.preferred_patterns = [
            r'PREFERRED',
            r'PREFERENCE',
            r'\.PR\.',
            r'\.PF\.',
        ]
        
        self.crypto_patterns = [
            r'\bBITCOIN\b',
            r'\bETHEREUM\b',
            r'\bSOLANA\b', 
            r'\bCRYPTO\b',
            r'\bBLOCKCHAIN\b',
        ]
        
        # Symbol suffix patterns for Canadian markets
        self.suffix_patterns = {
            '.UN': 'UNIT',      # Units (often REITs)
            '.U': 'OTHER',      # USD version
            '.DB': 'BOND',      # Debenture/Bond
            '.WT': 'WARRANT',   # Warrant
            '.RT': 'RIGHTS',    # Rights
            '.PR': 'PREFERRED', # Preferred
            '.TO': 'STOCK',     # Toronto (but this is usually not in our data)
        }

    def classify_by_name(self, name: str) -> str:
        """Classify asset by company/fund name patterns."""
        name_upper = name.upper()
        
        # Check ETF patterns first (most specific)
        for pattern in self.etf_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'ETF'
        
        # Check REIT patterns
        for pattern in self.reit_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'REIT'
        
        # Check crypto patterns
        for pattern in self.crypto_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'CRYPTO'
        
        # Check warrant patterns
        for pattern in self.warrant_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'WARRANT'
        
        # Check rights patterns
        for pattern in self.rights_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'RIGHTS'
        
        # Check preferred patterns
        for pattern in self.preferred_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'PREFERRED'
        
        # Check bond patterns
        for pattern in self.bond_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'BOND'
        
        # Check fund patterns (after ETF to avoid conflicts)
        for pattern in self.fund_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'MUTUAL_FUND'
        
        # Check trust patterns (after REIT to avoid conflicts)
        for pattern in self.trust_patterns:
            if re.search(pattern, name_upper, re.IGNORECASE):
                return 'TRUST'
        
        return 'STOCK'  # Default assumption

    def classify_by_symbol(self, symbol: str) -> str:
        """Classify asset by symbol patterns."""
        symbol_upper = symbol.upper()
        
        # Check for suffix patterns
        for suffix, asset_type in self.suffix_patterns.items():
            if symbol_upper.endswith(suffix):
                return asset_type
        
        # Special symbol patterns
        if re.match(r'^[A-Z]{1,4}\.UN$', symbol_upper):
            return 'UNIT'
        
        if re.match(r'^[A-Z]{1,4}\.WT$', symbol_upper):
            return 'WARRANT'
            
        return None  # No conclusive determination from symbol

    def classify_by_api(self, symbol: str, exchange: str) -> str:
        """Use yfinance API to get security type (optional, slower)."""
        try:
            # Construct ticker symbol for yfinance
            if exchange.upper() in ['TSX', 'TSXV']:
                ticker_symbol = f"{symbol}.TO"
            else:
                ticker_symbol = symbol
            
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            # yfinance security type mapping
            security_type = info.get('quoteType', '').lower()
            
            if security_type == 'etf':
                return 'ETF'
            elif security_type == 'mutualfund':
                return 'MUTUAL_FUND'
            elif security_type == 'equity':
                return 'STOCK'
            elif security_type in ['bond', 'fixed_income']:
                return 'BOND'
                
        except Exception as e:
            logger.debug(f"API classification failed for {symbol}: {e}")
        
        return None

    def classify_listing(self, listing: Listing, use_api: bool = False) -> str:
        """Classify a single listing using multiple methods."""
        
        # Method 1: Symbol-based classification
        symbol_classification = self.classify_by_symbol(listing.symbol)
        if symbol_classification and symbol_classification != 'OTHER':
            return symbol_classification
        
        # Method 2: Name-based classification
        name_classification = self.classify_by_name(listing.name)
        
        # Method 3: API-based classification (optional)
        api_classification = None
        if use_api:
            api_classification = self.classify_by_api(listing.symbol, listing.exchange)
        
        # Prioritize classifications
        if api_classification:
            return api_classification
        elif name_classification != 'STOCK':
            return name_classification
        elif symbol_classification:
            return symbol_classification
        else:
            return 'STOCK'  # Default

    def get_asset_type_stats(self) -> Dict[str, int]:
        """Get statistics of asset types in the database."""
        from django.db.models import Count
        
        # This will work after we add the asset_type field
        try:
            stats = Listing.objects.values('asset_type').annotate(
                count=Count('asset_type')
            ).order_by('-count')
            
            return {item['asset_type'] or 'UNCLASSIFIED': item['count'] for item in stats}
        
        except AttributeError:
            # If asset_type field doesn't exist yet
            return {}

    def classify_all_listings(self, use_api: bool = False, limit: int = None) -> Dict:
        """Classify all listings in the database."""
        
        queryset = Listing.objects.all()
        if limit:
            queryset = queryset[:limit]
            
        results = {
            'total_processed': 0,
            'classifications': {},
            'errors': []
        }
        
        for listing in queryset:
            try:
                asset_type = self.classify_listing(listing, use_api=use_api)
                
                # Update the listing with the classified asset type
                listing.asset_type = asset_type
                listing.save(update_fields=['asset_type'])
                
                # For now, just collect stats
                if asset_type not in results['classifications']:
                    results['classifications'][asset_type] = []
                
                results['classifications'][asset_type].append({
                    'symbol': listing.symbol,
                    'name': listing.name,
                    'exchange': listing.exchange
                })
                
                results['total_processed'] += 1
                
            except Exception as e:
                error_msg = f"Error classifying {listing.symbol}: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        return results


def demo_classification():
    """Demo function to test classification on sample data."""
    
    print("🔍 Asset Classification Demo")
    print("=" * 50)
    
    classifier = AssetClassifier()
    
    # Test with some example listings
    test_cases = [
        # Get some real data from the database
        ('XGRO', 'iShares Core Growth ETF Portfolio', 'TSX'),
        ('SHOP', 'Shopify Inc.', 'TSX'),
        ('DRR.UN', 'Dream Residnt REIT', 'TSX'),
        ('QBTC', 'Bitcoin Fund A CAD', 'TSX'),
        ('AAV.DB', 'Adv Engy5.0 USub Db', 'TSX'),
    ]
    
    print("📊 Sample Classifications:")
    for symbol, name, exchange in test_cases:
        # Create a temporary listing object for testing
        class TempListing:
            def __init__(self, symbol, name, exchange):
                self.symbol = symbol
                self.name = name
                self.exchange = exchange
        
        temp_listing = TempListing(symbol, name, exchange)
        classification = classifier.classify_listing(temp_listing)
        
        print(f"{symbol:8} | {classification:12} | {name[:40]}")
    
    print("\n🚀 Running classification on real database data...")
    
    # Classify a small sample of real data
    try:
        results = classifier.classify_all_listings(limit=20, use_api=False)
        
        print(f"\n📈 Results (Processed {results['total_processed']} items):")
        for asset_type, items in results['classifications'].items():
            print(f"\n{asset_type} ({len(items)} items):")
            for item in items[:5]:  # Show first 5 of each type
                print(f"  • {item['symbol']} - {item['name'][:40]}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more")
                
        if results['errors']:
            print(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors'][:3]:
                print(f"  • {error}")
                
    except Exception as e:
        print(f"Error running classification: {e}")
    
    return results


# Canadian Market Specific Classifications
def get_canadian_asset_patterns():
    """Return Canadian-specific asset classification patterns."""
    return {
        'tsx_etf_families': [
            'iShares', 'Vanguard', 'BMO', 'RBC', 'TD', 'Invesco QQQ', 
            'SPDR', 'PowerShares', 'First Asset', 'Horizons', 'CI', 'Evolve'
        ],
        'reit_suffixes': ['.UN', '.U'],
        'trust_keywords': ['Income Trust', 'Royalty Trust', 'Energy Trust'],
        'preferred_patterns': [r'\.PR\.', r'Series [A-Z]', r'Preferred'],
        'warrant_patterns': [r'\.WT', r'\.WS', r'Warrant'],
    }


if __name__ == '__main__':
    # Run demo if script is executed directly
    demo_classification()
