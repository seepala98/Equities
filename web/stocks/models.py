from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=16, db_index=True)
    date = models.DateField(null=True, blank=True)
    open_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    high_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    low_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    close_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']

    def __str__(self):
        return f"{self.symbol} {self.date or ''}"


class Listing(models.Model):
    EXCHANGE_CHOICES = (
        ('TSX', 'TSX'),
        ('TSXV', 'TSX Venture Exchange'),
    )

    # Asset type classification choices
    ASSET_TYPE_CHOICES = [
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

    exchange = models.CharField(max_length=8, choices=EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    
    # NEW: Asset classification field
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, 
                                 default='STOCK', db_index=True,
                                 help_text='Type of financial instrument')
    
    # status tracks whether the row is currently listed, recently listed, delisted or suspended
    STATUS_CHOICES = (
        ('listed', 'Currently Listed'),
        ('delisted', 'Recently Delisted'),
        ('suspended', 'Suspended'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='listed', db_index=True)
    # active is a convenience boolean: True when listed or recent, False for delisted/suspended
    active = models.BooleanField(default=True, db_index=True)
    # Optional date associated with the status (e.g. delisted date or suspension date)
    status_date = models.DateField(null=True, blank=True, help_text='Date when status (delisted/suspended) occurred')
    listing_url = models.URLField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('exchange', 'symbol')
        ordering = ['exchange', 'symbol']

    def __str__(self):
        return f"{self.exchange}:{self.symbol} — {self.name}"

class DelistedListing(models.Model):
    """Separate table for delisted entries to avoid modifying current stocks_listing flow."""
    exchange = models.CharField(max_length=8, choices=Listing.EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    listing_url = models.URLField(null=True, blank=True)
    delisted_date = models.DateField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']
        unique_together = ('exchange', 'symbol')

    def __str__(self):
        return f"{self.exchange}:{self.symbol} (delisted) — {self.name}"

class SuspendedListing(models.Model):
    """Separate table for suspended entries."""
    exchange = models.CharField(max_length=8, choices=Listing.EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    listing_url = models.URLField(null=True, blank=True)
    suspended_date = models.DateField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']
        unique_together = ('exchange', 'symbol')

    def __str__(self):
        return f"{self.exchange}:{self.symbol} (suspended) — {self.name}"


# ====================================================================
# ETF Holdings Models - Added for comprehensive ETF analysis
# ====================================================================

class Sector(models.Model):
    """Industry sectors for stock classification."""
    sector_name = models.CharField(max_length=100, unique=True)
    sector_code = models.CharField(max_length=10, blank=True, null=True, help_text="GICS sector code")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sector_name']
        db_table = 'sectors'

    def __str__(self):
        return self.sector_name


class GeographicRegion(models.Model):
    """Geographic regions for portfolio allocation."""
    REGION_TYPE_CHOICES = [
        ('Developed', 'Developed Markets'),
        ('Emerging', 'Emerging Markets'),
        ('Frontier', 'Frontier Markets'),
    ]
    
    region_name = models.CharField(max_length=100)  # Removed unique=True
    country_name = models.CharField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=8, blank=True, null=True, help_text="ISO country code")
    region_type = models.CharField(max_length=20, choices=REGION_TYPE_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['region_name', 'country_name']
        db_table = 'geographic_regions'
        # Allow same region name with different countries
        unique_together = [['region_name', 'country_name']]

    def __str__(self):
        if self.country_name:
            return f"{self.region_name} - {self.country_name}"
        return self.region_name


class ETFInfo(models.Model):
    """Basic ETF information and metadata."""
    CURRENCY_CHOICES = [
        ('CAD', 'Canadian Dollar'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
    ]
    
    FREQUENCY_CHOICES = [
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Semi-Annual', 'Semi-Annual'),
        ('Annual', 'Annual'),
    ]

    symbol = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    isin = models.CharField(max_length=32, blank=True, null=True, help_text="International Securities ID")
    expense_ratio = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True, 
                                      help_text="Management Expense Ratio (MER)")
    assets_under_management = models.BigIntegerField(blank=True, null=True, help_text="Total AUM in dollars")
    inception_date = models.DateField(blank=True, null=True)
    fund_family = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Vanguard, iShares")
    category = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Equity, Bond, Balanced")
    investment_strategy = models.TextField(blank=True, null=True)
    benchmark_index = models.CharField(max_length=255, blank=True, null=True)
    currency = models.CharField(max_length=8, choices=CURRENCY_CHOICES, default='CAD')
    domicile = models.CharField(max_length=8, default='CA', help_text="Country of domicile")
    distribution_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['symbol']
        db_table = 'etf_info'
        verbose_name = "ETF Information"
        verbose_name_plural = "ETF Information"

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    @property
    def aum_formatted(self):
        """Format AUM in billions/millions."""
        if not self.assets_under_management:
            return "N/A"
        
        aum = self.assets_under_management
        if aum >= 1_000_000_000:
            return f"${aum / 1_000_000_000:.2f}B"
        elif aum >= 1_000_000:
            return f"${aum / 1_000_000:.1f}M"
        else:
            return f"${aum:,}"

    @property
    def mer_formatted(self):
        """Format MER as percentage."""
        if not self.expense_ratio:
            return "N/A"
        return f"{float(self.expense_ratio):.2f}%"


class StockDetail(models.Model):
    """Enhanced stock information extending the existing stocks_listing."""
    # Link to existing stocks_listing table
    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='detail')
    sector = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True)
    region = models.ForeignKey(GeographicRegion, on_delete=models.SET_NULL, null=True, blank=True)
    
    market_cap = models.BigIntegerField(blank=True, null=True, help_text="Market capitalization in dollars")
    industry = models.CharField(max_length=150, blank=True, null=True, help_text="More specific than sector")
    headquarters_country = models.CharField(max_length=100, blank=True, null=True)
    business_description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_details'
        verbose_name = "Stock Detail"
        verbose_name_plural = "Stock Details"

    def __str__(self):
        return f"{self.listing.symbol} - {self.listing.name}"

    @property
    def market_cap_formatted(self):
        """Format market cap in billions/millions."""
        if not self.market_cap:
            return "N/A"
        
        cap = self.market_cap
        if cap >= 1_000_000_000:
            return f"${cap / 1_000_000_000:.2f}B"
        elif cap >= 1_000_000:
            return f"${cap / 1_000_000:.1f}M"
        else:
            return f"${cap:,}"


class ETFHolding(models.Model):
    """Main table storing ETF-to-stock relationships with weights."""
    etf = models.ForeignKey(ETFInfo, on_delete=models.CASCADE, related_name='holdings')
    stock_listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='etf_holdings')
    
    weight_percentage = models.DecimalField(max_digits=8, decimal_places=4, 
                                          help_text="Percentage weight in ETF (e.g., 5.25)")
    shares_held = models.BigIntegerField(blank=True, null=True, help_text="Number of shares held")
    market_value = models.BigIntegerField(blank=True, null=True, help_text="Market value of holding in dollars")
    as_of_date = models.DateField(help_text="Holdings as of this date")
    data_source = models.CharField(max_length=50, blank=True, null=True, 
                                 help_text="Where data came from (e.g., yfinance, vanguard)")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensure no duplicate holdings for same ETF on same date
        unique_together = [['etf', 'stock_listing', 'as_of_date']]
        ordering = ['-weight_percentage']
        db_table = 'etf_holdings'
        indexes = [
            models.Index(fields=['etf', '-weight_percentage']),
            models.Index(fields=['as_of_date']),
        ]

    def __str__(self):
        return f"{self.etf.symbol}: {self.stock_listing.symbol} ({self.weight_percentage}%)"

    @property
    def weight_formatted(self):
        """Format weight as percentage string."""
        return f"{float(self.weight_percentage):.2f}%"

    @property
    def market_value_formatted(self):
        """Format market value with commas."""
        if not self.market_value:
            return "N/A"
        return f"${self.market_value:,}"


class ETFSectorAllocation(models.Model):
    """Aggregated sector allocation for ETFs."""
    etf = models.ForeignKey(ETFInfo, on_delete=models.CASCADE, related_name='sector_allocations')
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE)
    allocation_percentage = models.DecimalField(max_digits=8, decimal_places=4)
    as_of_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['etf', 'sector', 'as_of_date']]
        ordering = ['-allocation_percentage']
        db_table = 'etf_sector_allocation'

    def __str__(self):
        return f"{self.etf.symbol}: {self.sector.sector_name} ({self.allocation_percentage}%)"

    @property
    def allocation_formatted(self):
        return f"{float(self.allocation_percentage):.1f}%"


class ETFGeographicAllocation(models.Model):
    """Geographic allocation for ETFs."""
    etf = models.ForeignKey(ETFInfo, on_delete=models.CASCADE, related_name='geographic_allocations')
    region = models.ForeignKey(GeographicRegion, on_delete=models.CASCADE)
    allocation_percentage = models.DecimalField(max_digits=8, decimal_places=4)
    as_of_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['etf', 'region', 'as_of_date']]
        ordering = ['-allocation_percentage']
        db_table = 'etf_geographic_allocation'

    def __str__(self):
        return f"{self.etf.symbol}: {self.region.region_name} ({self.allocation_percentage}%)"

    @property
    def allocation_formatted(self):
        return f"{float(self.allocation_percentage):.1f}%"


# ====================================================================  
# YFinance Sector Caching Models - Added for efficient data retrieval
# ====================================================================

class YFinanceSectorCache(models.Model):
    """Cache yfinance sector data to avoid repeated API calls."""
    
    # Sector identification
    sector_key = models.CharField(max_length=50, unique=True, db_index=True,
                                 help_text="yfinance sector key (e.g., 'technology')")
    sector_name = models.CharField(max_length=100, help_text="Human-readable sector name")
    
    # Core sector information
    symbol = models.CharField(max_length=20, blank=True, null=True)
    overview = models.TextField(blank=True, null=True, help_text="Sector overview/description")
    
    # Data availability flags (for template safety)
    has_top_etfs = models.BooleanField(default=False)
    has_top_companies = models.BooleanField(default=False)  
    has_top_mutual_funds = models.BooleanField(default=False)
    has_industries = models.BooleanField(default=False)
    has_research_reports = models.BooleanField(default=False)
    
    # Cached data (stored as JSON)
    top_etfs_data = models.JSONField(blank=True, null=True, help_text="Cached top ETFs data")
    top_companies_data = models.JSONField(blank=True, null=True, help_text="Cached top companies data")
    top_mutual_funds_data = models.JSONField(blank=True, null=True, help_text="Cached mutual funds data")
    industries_data = models.JSONField(blank=True, null=True, help_text="Cached industries data")
    research_reports_data = models.JSONField(blank=True, null=True, help_text="Cached research reports")
    
    # Cache metadata
    data_fetched_at = models.DateTimeField(auto_now_add=True, help_text="When data was fetched from yfinance")
    last_updated = models.DateTimeField(auto_now=True, help_text="Last update timestamp")
    fetch_error = models.TextField(blank=True, null=True, help_text="Last fetch error if any")
    fetch_success = models.BooleanField(default=True, help_text="Whether last fetch was successful")
    
    class Meta:
        db_table = 'yfinance_sector_cache'
        ordering = ['sector_name']
        verbose_name = "YFinance Sector Cache"
        verbose_name_plural = "YFinance Sector Cache"
    
    def __str__(self):
        return f"{self.sector_name} (cached {self.data_fetched_at.strftime('%Y-%m-%d %H:%M') if self.data_fetched_at else 'never'})"
    
    @property
    def is_cache_fresh(self):
        """Check if cached data is still fresh (within 24 hours)."""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.data_fetched_at:
            return False
        
        cache_expires_at = self.data_fetched_at + timedelta(hours=24)
        return timezone.now() < cache_expires_at
    
    def to_sector_data_dict(self):
        """Convert cached data back to the format expected by sector analysis."""
        return {
            'key': self.sector_key,
            'name': self.sector_name,
            'symbol': self.symbol,
            'overview': self.overview,
            'success': self.fetch_success,
            'has_top_etfs': self.has_top_etfs,
            'has_top_companies': self.has_top_companies,
            'has_top_mutual_funds': self.has_top_mutual_funds,
            'has_industries': self.has_industries,
            'has_research_reports': self.has_research_reports,
            'top_etfs': self.top_etfs_data,
            'top_companies': self.top_companies_data,
            'top_mutual_funds': self.top_mutual_funds_data,
            'industries': self.industries_data,
            'research_reports': self.research_reports_data,
            'from_cache': True
        }


class YFinanceStockSectorCache(models.Model):
    """Cache stock sector/industry data to avoid repeated API calls."""
    
    symbol = models.CharField(max_length=32, unique=True, db_index=True)
    
    # Sector/industry information
    sector = models.CharField(max_length=100, blank=True, null=True)
    industry = models.CharField(max_length=150, blank=True, null=True)
    sector_key = models.CharField(max_length=50, blank=True, null=True)
    industry_key = models.CharField(max_length=50, blank=True, null=True)
    
    # Cache metadata
    data_fetched_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    fetch_success = models.BooleanField(default=True)
    fetch_error = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'yfinance_stock_sector_cache'
        ordering = ['symbol']
        verbose_name = "Stock Sector Cache"
        verbose_name_plural = "Stock Sector Cache"
    
    def __str__(self):
        return f"{self.symbol} → {self.sector or 'Unknown'}"
    
    @property
    def is_cache_fresh(self):
        """Check if cached data is still fresh (within 7 days)."""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.data_fetched_at:
            return False
        
        cache_expires_at = self.data_fetched_at + timedelta(days=7)
        return timezone.now() < cache_expires_at
    
    def to_stock_analysis_dict(self):
        """Convert to format expected by stock analysis."""
        return {
            'symbol': self.symbol,
            'sector': self.sector,
            'industry': self.industry,
            'sector_key': self.sector_key,
            'industry_key': self.industry_key,
            'success': self.fetch_success,
            'from_cache': True
        }


# ====================================================================  
# Enriched Ticker Data Model - For weekly DAG population
# ====================================================================

class EnrichedTickerData(models.Model):
    """
    Comprehensive ticker information populated by weekly Airflow DAG.
    Combines asset classification, sector analysis, and regional data.
    """
    
    # Core ticker information
    symbol = models.CharField(max_length=32, db_index=True, help_text="Stock symbol (e.g., AAPL, SHOP.TO)")
    exchange = models.CharField(max_length=20, blank=True, null=True, help_text="Stock exchange")
    company_name = models.CharField(max_length=200, blank=True, null=True, help_text="Company name")
    
    # Asset classification
    ASSET_TYPE_CHOICES = [
        ('STOCK', 'Individual Stock'), ('ETF', 'Exchange Traded Fund'),
        ('MUTUAL_FUND', 'Mutual Fund'), ('REIT', 'Real Estate Investment Trust'),
        ('TRUST', 'Business/Income Trust'), ('BOND', 'Bond/Fixed Income'),
        ('WARRANT', 'Warrant'), ('RIGHTS', 'Rights'), ('PREFERRED', 'Preferred Share'),
        ('UNIT', 'Unit/Hybrid Security'), ('CRYPTO', 'Cryptocurrency Product'),
        ('COMMODITY', 'Commodity Fund'), ('OTHER', 'Other/Unknown'),
    ]
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES, 
                                 default='OTHER', db_index=True)
    asset_confidence = models.FloatField(default=0.0, help_text="Confidence score for asset classification (0-1)")
    
    # Sector and industry information
    sector = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    industry = models.CharField(max_length=150, blank=True, null=True, db_index=True)
    sector_key = models.CharField(max_length=50, blank=True, null=True, 
                                 help_text="yfinance sector key for detailed analysis")
    industry_key = models.CharField(max_length=50, blank=True, null=True,
                                   help_text="yfinance industry key")
    
    # Geographic information
    country = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    country_code = models.CharField(max_length=8, blank=True, null=True, help_text="ISO country code")
    region = models.CharField(max_length=100, blank=True, null=True, db_index=True,
                             help_text="Geographic region (North America, Europe, etc.)")
    
    # Market data
    market_cap = models.BigIntegerField(blank=True, null=True, help_text="Market capitalization in USD")
    currency = models.CharField(max_length=10, blank=True, null=True, help_text="Trading currency")
    is_active = models.BooleanField(default=True, help_text="Whether the ticker is actively trading")
    
    # Data quality and source tracking
    data_source = models.CharField(max_length=50, default='yfinance', 
                                  help_text="Primary data source used")
    data_quality_score = models.FloatField(default=0.0, 
                                          help_text="Overall data completeness score (0-1)")
    fetch_success = models.BooleanField(default=True, help_text="Whether data fetch was successful")
    fetch_errors = models.JSONField(blank=True, null=True, help_text="Any errors encountered during fetch")
    
    # Timestamp tracking for change detection
    first_loaded_at = models.DateTimeField(auto_now_add=True, help_text="When this ticker was first processed")
    last_updated_at = models.DateTimeField(auto_now=True, help_text="When this record was last updated")
    last_checked_at = models.DateTimeField(auto_now=True, help_text="When this ticker was last checked by DAG")
    data_changed_at = models.DateTimeField(blank=True, null=True, 
                                          help_text="When the ticker data last actually changed")
    
    # Version tracking for change detection
    data_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True,
                                help_text="Hash of key data fields for change detection")
    version = models.IntegerField(default=1, help_text="Version number, incremented on changes")
    
    class Meta:
        db_table = 'enriched_ticker_data'
        ordering = ['symbol']
        unique_together = [['symbol', 'version']]  # Allow multiple versions for history
        indexes = [
            models.Index(fields=['symbol', '-version']),  # Latest version lookup
            models.Index(fields=['asset_type', 'sector']),  # Analysis queries
            models.Index(fields=['country', 'region']),  # Geographic queries
            models.Index(fields=['last_checked_at']),  # DAG processing
            models.Index(fields=['data_hash']),  # Change detection
        ]
        verbose_name = "Enriched Ticker Data"
        verbose_name_plural = "Enriched Ticker Data"
    
    def __str__(self):
        return f"{self.symbol} v{self.version} ({self.asset_type}) - {self.sector or 'Unknown Sector'}"
    
    def calculate_data_hash(self):
        """Calculate hash of key data fields for change detection."""
        import hashlib
        
        # Include all the fields that matter for change detection
        key_data = {
            'asset_type': self.asset_type,
            'sector': self.sector,
            'industry': self.industry,
            'country': self.country,
            'region': self.region,
            'market_cap': self.market_cap,
            'currency': self.currency,
            'is_active': self.is_active,
        }
        
        # Convert to sorted string representation for consistent hashing
        data_str = str(sorted(key_data.items()))
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def save(self, *args, **kwargs):
        """Override save to calculate data hash automatically."""
        self.data_hash = self.calculate_data_hash()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_latest_version(cls, symbol: str):
        """Get the latest version of data for a symbol."""
        return cls.objects.filter(symbol=symbol.upper()).order_by('-version').first()
    
    @classmethod
    def has_data_changed(cls, symbol: str, new_data: dict) -> bool:
        """Check if new data is different from the latest version."""
        latest = cls.get_latest_version(symbol)
        if not latest:
            return True  # No existing data, so it's "changed"
        
        # Create temporary instance to calculate hash of new data
        temp_instance = cls(symbol=symbol, **new_data)
        new_hash = temp_instance.calculate_data_hash()
        
        return latest.data_hash != new_hash
    
    @classmethod
    def create_new_version(cls, symbol: str, data: dict):
        """Create a new version if data has changed."""
        from django.utils import timezone
        
        if not cls.has_data_changed(symbol, data):
            # Update last_checked_at on existing record
            latest = cls.get_latest_version(symbol)
            if latest:
                latest.last_checked_at = timezone.now()
                latest.save(update_fields=['last_checked_at'])
            return latest, False  # No new version created
        
        # Data has changed, create new version
        latest = cls.get_latest_version(symbol)
        new_version = (latest.version + 1) if latest else 1
        
        # Create new record
        new_record = cls(
            symbol=symbol.upper(),
            version=new_version,
            data_changed_at=timezone.now(),
            **data
        )
        new_record.save()
        
        return new_record, True  # New version created
    
    @property
    def data_completeness_score(self):
        """Calculate how complete this ticker's data is (0-1)."""
        total_fields = 12  # Key fields we care about
        filled_fields = 0
        
        if self.company_name: filled_fields += 1
        if self.asset_type != 'OTHER': filled_fields += 1
        if self.sector: filled_fields += 1
        if self.industry: filled_fields += 1
        if self.sector_key: filled_fields += 1
        if self.country: filled_fields += 1
        if self.region: filled_fields += 1
        if self.market_cap: filled_fields += 1
        if self.currency: filled_fields += 1
        if self.data_source: filled_fields += 1
        if self.fetch_success: filled_fields += 1
        if not self.fetch_errors: filled_fields += 1
        
        return filled_fields / total_fields
    
    @property
    def is_stale(self):
        """Check if this data is considered stale (older than 7 days)."""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.last_checked_at:
            return True
        
        stale_threshold = timezone.now() - timedelta(days=7)
        return self.last_checked_at < stale_threshold
