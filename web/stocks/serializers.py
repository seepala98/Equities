from rest_framework import serializers
from .models import (
    Stock,
    Listing,
    DelistedListing,
    ETFInfo,
    ETFHolding,
    Sector,
    GeographicRegion,
    ETFSectorAllocation,
    ETFGeographicAllocation,
    EnrichedTickerData,
    Portfolio,
    Transaction,
    PortfolioHolding,
    PortfolioCashSummary,
    HistoricalPrice,
    IntradayPrice,
)


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = [
            "id",
            "symbol",
            "date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "scraped_at",
        ]


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = [
            "id",
            "exchange",
            "symbol",
            "name",
            "asset_type",
            "status",
            "active",
            "status_date",
            "scraped_at",
        ]


class DelistedListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DelistedListing
        fields = ["id", "exchange", "symbol", "name", "delisted_date", "scraped_at"]


class SectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sector
        fields = ["id", "sector_name", "sector_code", "description"]


class GeographicRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeographicRegion
        fields = ["id", "region_name", "country_name", "country_code", "region_type"]


class ETFInfoSerializer(serializers.ModelSerializer):
    aum_formatted = serializers.ReadOnlyField()
    mer_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFInfo
        fields = [
            "id",
            "symbol",
            "name",
            "isin",
            "expense_ratio",
            "mer_formatted",
            "assets_under_management",
            "aum_formatted",
            "inception_date",
            "fund_family",
            "category",
            "investment_strategy",
            "benchmark_index",
            "currency",
            "domicile",
            "distribution_frequency",
            "updated_at",
        ]


class ETFHoldingSerializer(serializers.ModelSerializer):
    stock_symbol = serializers.CharField(source="stock_listing.symbol", read_only=True)
    stock_name = serializers.CharField(source="stock_listing.name", read_only=True)
    stock_exchange = serializers.CharField(
        source="stock_listing.exchange", read_only=True
    )
    weight_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFHolding
        fields = [
            "id",
            "stock_symbol",
            "stock_name",
            "stock_exchange",
            "weight_percentage",
            "weight_formatted",
            "shares_held",
            "market_value",
            "as_of_date",
            "data_source",
        ]


class ETFSectorAllocationSerializer(serializers.ModelSerializer):
    sector_name = serializers.CharField(source="sector.sector_name", read_only=True)
    allocation_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFSectorAllocation
        fields = [
            "sector_name",
            "allocation_percentage",
            "allocation_formatted",
            "as_of_date",
        ]


class ETFGeographicAllocationSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.region_name", read_only=True)
    country_name = serializers.CharField(source="region.country_name", read_only=True)
    allocation_formatted = serializers.ReadOnlyField()

    class Meta:
        model = ETFGeographicAllocation
        fields = [
            "region_name",
            "country_name",
            "allocation_percentage",
            "allocation_formatted",
            "as_of_date",
        ]


class ETFDetailSerializer(ETFInfoSerializer):
    """ETFInfo with inline holdings, sector, and geographic allocations."""

    holdings = ETFHoldingSerializer(many=True, read_only=True)
    sector_allocations = ETFSectorAllocationSerializer(many=True, read_only=True)
    geographic_allocations = ETFGeographicAllocationSerializer(
        many=True, read_only=True
    )

    class Meta(ETFInfoSerializer.Meta):
        fields = ETFInfoSerializer.Meta.fields + [
            "holdings",
            "sector_allocations",
            "geographic_allocations",
        ]


class EnrichedTickerSerializer(serializers.ModelSerializer):
    data_completeness_score = serializers.ReadOnlyField()
    is_stale = serializers.ReadOnlyField()

    class Meta:
        model = EnrichedTickerData
        fields = [
            "id",
            "symbol",
            "exchange",
            "company_name",
            "asset_type",
            "asset_confidence",
            "sector",
            "industry",
            "sector_key",
            "country",
            "region",
            "market_cap",
            "currency",
            "is_active",
            "data_source",
            "data_quality_score",
            "data_completeness_score",
            "is_stale",
            "version",
            "last_updated_at",
        ]


class ETFPerformanceSerializer(serializers.Serializer):
    """For the performance calculation endpoint."""

    symbol = serializers.CharField()
    investment_amount = serializers.FloatField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)


class PortfolioSerializer(serializers.ModelSerializer):
    holdings_count = serializers.SerializerMethodField()
    total_invested = serializers.SerializerMethodField()

    class Meta:
        model = Portfolio
        fields = [
            "id",
            "name",
            "account_type",
            "institution",
            "account_number",
            "created_at",
            "updated_at",
            "holdings_count",
            "total_invested",
        ]

    def get_holdings_count(self, obj):
        from django.db.models import Sum

        result = (
            obj.transactions.filter(transaction_type__in=["BUY", "DRIP"])
            .values("symbol")
            .annotate(total_shares=Sum("quantity"))
            .filter(total_shares__gt=0)
        )
        return len(list(result))

    def get_total_invested(self, obj):
        from django.db.models import Sum, Q

        result = obj.transactions.filter(
            Q(transaction_type="BUY") | Q(transaction_type="DRIP")
        ).aggregate(total=Sum("amount"))
        return float(result["total"] or 0)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "symbol",
            "transaction_type",
            "date",
            "execution_date",
            "quantity",
            "price",
            "amount",
            "balance",
            "currency",
            "description",
            "is_drip",
            "statement_period",
            "imported_at",
        ]


class TransactionPreviewSerializer(serializers.Serializer):
    """For previewing parsed transactions before saving."""

    symbol = serializers.CharField(allow_blank=True, allow_null=True)
    transaction_type = serializers.CharField()
    date = serializers.DateField()
    execution_date = serializers.DateField(allow_null=True)
    quantity = serializers.DecimalField(
        max_digits=18, decimal_places=8, allow_null=True
    )
    price = serializers.DecimalField(max_digits=18, decimal_places=6, allow_null=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    balance = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    currency = serializers.CharField(default="CAD")
    description = serializers.CharField(allow_blank=True)
    is_drip = serializers.BooleanField(default=False)
    warnings = serializers.ListField(child=serializers.CharField(), default=[])


class ParseResultSerializer(serializers.Serializer):
    """Result of parsing a portfolio file."""

    detected_account_type = serializers.CharField(allow_null=True)
    detected_account_number = serializers.CharField(allow_null=True)
    statement_period = serializers.CharField(allow_blank=True)
    transactions = TransactionPreviewSerializer(many=True)
    summary = serializers.DictField()
    errors = serializers.ListField(child=serializers.CharField(), default=[])
    holdings = serializers.ListField(default=[])
    cash_summary = serializers.DictField(default={})
    stock_lending = serializers.ListField(default=[])


class HoldingSerializer(serializers.Serializer):
    """Current holding with P&L."""

    symbol = serializers.CharField()
    total_shares = serializers.DecimalField(max_digits=18, decimal_places=8)
    avg_cost = serializers.DecimalField(max_digits=18, decimal_places=6)
    total_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    current_price = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    current_value = serializers.DecimalField(
        max_digits=18, decimal_places=2, allow_null=True
    )
    gain_loss = serializers.DecimalField(max_digits=18, decimal_places=2)
    gain_loss_pct = serializers.DecimalField(max_digits=10, decimal_places=2)
    dividends_received = serializers.DecimalField(max_digits=18, decimal_places=2)


class PerformanceSerializer(serializers.Serializer):
    """Portfolio performance over date range."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_invested = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_current_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_gain_loss = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_gain_loss_pct = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_dividends = serializers.DecimalField(max_digits=18, decimal_places=2)
    holdings = HoldingSerializer(many=True)
    daily_values = serializers.ListField()


class PortfolioHoldingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioHolding
        fields = [
            "id",
            "symbol",
            "name",
            "quantity",
            "segregated_quantity",
            "market_price",
            "market_value",
            "book_cost",
            "statement_period",
        ]


class PortfolioCashSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioCashSummary
        fields = [
            "id",
            "last_statement_cash_balance",
            "total_cash_paid_in",
            "total_cash_paid_out",
            "closing_cash_balance",
            "contributions_ytd",
            "statement_period",
        ]


class HistoricalPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricalPrice
        fields = [
            "id",
            "symbol",
            "date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "adj_close",
            "volume",
            "currency",
            "fetched_at",
        ]


class IntradayPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntradayPrice
        fields = [
            "id",
            "symbol",
            "timestamp",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "interval",
            "fetched_at",
        ]
