"""
ETF Holdings Models
Extends the existing stocks system with comprehensive ETF composition data
"""
from django.db import models
from decimal import Decimal


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
    
    region_name = models.CharField(max_length=100, unique=True)
    country_name = models.CharField(max_length=100, blank=True, null=True)
    country_code = models.CharField(max_length=8, blank=True, null=True, help_text="ISO country code")
    region_type = models.CharField(max_length=20, choices=REGION_TYPE_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['region_name', 'country_name']
        db_table = 'geographic_regions'

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
    listing = models.OneToOneField('Listing', on_delete=models.CASCADE, related_name='detail')
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
    stock_listing = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='etf_holdings')
    
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
