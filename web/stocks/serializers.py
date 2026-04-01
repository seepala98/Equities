from rest_framework import serializers
from .models import (
    Stock, Listing, DelistedListing, ETFInfo, ETFHolding,
    Sector, GeographicRegion, ETFSectorAllocation, ETFGeographicAllocation,
    EnrichedTickerData,
)


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['id', 'symbol', 'date', 'open_price', 'high_price', 'low_price',
                  'close_price', 'volume', 'scraped_at']


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['id', 'exchange', 'symbol', 'name', 'asset_type', 'status', 'active',
                  'status_date', 'scraped_at']


class DelistedListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DelistedListing
        fields = ['id', 'exchange', 'symbol', 'name', 'delisted_date', 'scraped_at']


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = ['id', 'sector_name', 'sector_code', 'description']


class GeographicRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeographicRegion
        fields = ['id', 'region_name', 'country_name', 'country_code', 'region_type']


class ETFInfoSerializer(serializers.ModelSerializer):
    aum_formatted = serializers.ReadOnlyField()
    mer_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFInfo
        fields = ['id', 'symbol', 'name', 'isin', 'expense_ratio', 'mer_formatted',
                  'assets_under_management', 'aum_formatted', 'inception_date',
                  'fund_family', 'category', 'investment_strategy', 'benchmark_index',
                  'currency', 'domicile', 'distribution_frequency', 'updated_at']


class ETFHoldingSerializer(serializers.ModelSerializer):
    stock_symbol = serializers.CharField(source='stock_listing.symbol', read_only=True)
    stock_name = serializers.CharField(source='stock_listing.name', read_only=True)
    stock_exchange = serializers.CharField(source='stock_listing.exchange', read_only=True)
    weight_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFHolding
        fields = ['id', 'stock_symbol', 'stock_name', 'stock_exchange',
                  'weight_percentage', 'weight_formatted', 'shares_held',
                  'market_value', 'as_of_date', 'data_source']


class ETFSectorAllocationSerializer(serializers.ModelSerializer):
    sector_name = serializers.CharField(source='sector.sector_name', read_only=True)
    allocation_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFSectorAllocation
        fields = ['sector_name', 'allocation_percentage', 'allocation_formatted', 'as_of_date']


class ETFGeographicAllocationSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source='region.region_name', read_only=True)
    country_name = serializers.CharField(source='region.country_name', read_only=True)
    allocation_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFGeographicAllocation
        fields = ['region_name', 'country_name', 'allocation_percentage',
                  'allocation_formatted', 'as_of_date']


class ETFDetailSerializer(ETFInfoSerializer):
    """ETFInfo with inline holdings, sector, and geographic allocations."""
    holdings = ETFHoldingSerializer(many=True, read_only=True)
    sector_allocations = ETFSectorAllocationSerializer(many=True, read_only=True)
    geographic_allocations = ETFGeographicAllocationSerializer(many=True, read_only=True)

    class Meta(ETFInfoSerializer.Meta):
        fields = ETFInfoSerializer.Meta.fields + ['holdings', 'sector_allocations', 'geographic_allocations']


class EnrichedTickerSerializer(serializers.ModelSerializer):
    data_completeness_score = serializers.ReadOnlyField()
    is_stale = serializers.ReadOnlyField()

    class Meta:
        model = EnrichedTickerData
        fields = ['id', 'symbol', 'exchange', 'company_name', 'asset_type', 'asset_confidence',
                  'sector', 'industry', 'sector_key', 'country', 'region', 'market_cap',
                  'currency', 'is_active', 'data_source', 'data_quality_score',
                  'data_completeness_score', 'is_stale', 'version', 'last_updated_at']


class ETFPerformanceSerializer(serializers.Serializer):
    """For the performance calculation endpoint."""
    symbol = serializers.CharField()
    investment_amount = serializers.FloatField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
