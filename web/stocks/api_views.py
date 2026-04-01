"""
DRF API views for all major resources.
All list endpoints support pagination (PAGE_SIZE=50), search, and ordering.
"""
from django.core.cache import cache
from django.db.models import Count, Prefetch
from rest_framework import generics, filters, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Stock, Listing, DelistedListing, ETFInfo, ETFHolding,
    Sector, GeographicRegion, EnrichedTickerData,
)
from .serializers import (
    StockSerializer, ListingSerializer, DelistedListingSerializer,
    ETFInfoSerializer, ETFDetailSerializer, ETFHoldingSerializer,
    SectorSerializer, GeographicRegionSerializer, EnrichedTickerSerializer,
    ETFPerformanceSerializer,
)
from .etf_utils import calculate_investment_performance, get_popular_canadian_etfs
from .etf_holdings_utils import fetch_and_store_etf

# ---------------------------------------------------------------------------
# Stocks
# ---------------------------------------------------------------------------

class StockListView(generics.ListAPIView):
    serializer_class = StockSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol']
    ordering_fields = ['symbol', 'date', 'close_price', 'scraped_at']
    ordering = ['-scraped_at']

    def get_queryset(self):
        qs = Stock.objects.all()
        symbol = self.request.query_params.get('symbol')
        if symbol:
            qs = qs.filter(symbol=symbol.upper())
        return qs


@api_view(['GET'])
def stock_latest(request, symbol):
    """Return latest price record for a symbol."""
    item = Stock.objects.filter(symbol=symbol.upper()).order_by('-scraped_at').first()
    if not item:
        return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(StockSerializer(item).data)


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------

class ListingListView(generics.ListAPIView):
    serializer_class = ListingSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol', 'name']
    ordering_fields = ['symbol', 'name', 'exchange', 'asset_type']
    ordering = ['exchange', 'symbol']

    def get_queryset(self):
        qs = Listing.objects.only(
            'id', 'exchange', 'symbol', 'name', 'asset_type', 'status', 'active', 'status_date', 'scraped_at'
        )
        exchange = self.request.query_params.get('exchange')
        asset_type = self.request.query_params.get('asset_type')
        active = self.request.query_params.get('active')
        if exchange:
            qs = qs.filter(exchange=exchange.upper())
        if asset_type:
            qs = qs.filter(asset_type=asset_type.upper())
        if active is not None:
            qs = qs.filter(active=active.lower() in ('1', 'true', 'yes'))
        return qs


class DelistedListingListView(generics.ListAPIView):
    serializer_class = DelistedListingSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol', 'name']
    ordering = ['-delisted_date']

    def get_queryset(self):
        qs = DelistedListing.objects.all()
        exchange = self.request.query_params.get('exchange')
        if exchange:
            qs = qs.filter(exchange=exchange.upper())
        return qs


# ---------------------------------------------------------------------------
# Asset type summary
# ---------------------------------------------------------------------------

@api_view(['GET'])
def asset_type_summary(request):
    """Aggregated count of listings by asset type and exchange."""
    cache_key = 'api:asset_type_summary'
    data = cache.get(cache_key)
    if data is None:
        data = list(
            Listing.objects.values('exchange', 'asset_type')
            .annotate(count=Count('id'))
            .order_by('exchange', '-count')
        )
        cache.set(cache_key, data, timeout=600)  # 10 minutes
    return Response(data)


# ---------------------------------------------------------------------------
# ETFs
# ---------------------------------------------------------------------------

class ETFListView(generics.ListAPIView):
    serializer_class = ETFInfoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol', 'name', 'fund_family', 'category']
    ordering_fields = ['symbol', 'assets_under_management', 'expense_ratio']
    ordering = ['symbol']
    queryset = ETFInfo.objects.all()


class ETFDetailView(generics.RetrieveAPIView):
    serializer_class = ETFDetailSerializer
    lookup_field = 'symbol'
    lookup_url_kwarg = 'symbol'

    def get_object(self):
        symbol = self.kwargs['symbol'].upper()
        cache_key = f'api:etf_detail:{symbol}'
        # Cache the queryset result, not the serialized data, so we can still serialize fresh
        qs = ETFInfo.objects.filter(symbol=symbol).prefetch_related(
            Prefetch('holdings', queryset=ETFHolding.objects.select_related('stock_listing').order_by('-weight_percentage')),
            'sector_allocations__sector',
            'geographic_allocations__region',
        )
        obj = qs.first()
        if obj is None:
            from rest_framework.exceptions import NotFound
            raise NotFound(f'ETF {symbol} not found.')
        return obj


class ETFHoldingsView(generics.ListAPIView):
    serializer_class = ETFHoldingSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['weight_percentage', 'as_of_date']
    ordering = ['-weight_percentage']

    def get_queryset(self):
        symbol = self.kwargs['symbol'].upper()
        return ETFHolding.objects.filter(
            etf__symbol=symbol
        ).select_related('stock_listing').order_by('-weight_percentage')


@api_view(['POST'])
def etf_fetch(request, symbol):
    """Trigger a fresh fetch of ETF data from yfinance and store it."""
    result = fetch_and_store_etf(symbol.upper())
    status_code = status.HTTP_200_OK if result['success'] else status.HTTP_502_BAD_GATEWAY
    return Response(result, status=status_code)


# ---------------------------------------------------------------------------
# ETF Performance
# ---------------------------------------------------------------------------

@api_view(['GET', 'POST'])
def etf_performance(request):
    """
    Calculate investment performance for an ETF.
    GET  ?symbol=XGRO&investment_amount=10000&start_date=2020-01-01
    POST { symbol, investment_amount, start_date, end_date }
    """
    params = request.query_params if request.method == 'GET' else request.data
    serializer = ETFPerformanceSerializer(data=params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    cache_key = (
        f"api:perf:{data['symbol']}:{data['investment_amount']}"
        f":{data['start_date']}:{data.get('end_date', 'today')}"
    )
    result = cache.get(cache_key)
    if result is None:
        try:
            result = calculate_investment_performance(
                symbol=data['symbol'],
                investment_amount=data['investment_amount'],
                start_date=str(data['start_date']),
                end_date=str(data['end_date']) if data.get('end_date') else None,
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cache.set(cache_key, result, timeout=3600)  # 1 hour

    return Response(result)


@api_view(['GET'])
def popular_etfs(request):
    """Return the list of popular Canadian ETFs."""
    return Response(get_popular_canadian_etfs())


# ---------------------------------------------------------------------------
# Sectors & Regions
# ---------------------------------------------------------------------------

class SectorListView(generics.ListAPIView):
    serializer_class = SectorSerializer
    queryset = Sector.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['sector_name']


class GeographicRegionListView(generics.ListAPIView):
    serializer_class = GeographicRegionSerializer
    queryset = GeographicRegion.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['region_name', 'country_name']


# ---------------------------------------------------------------------------
# Enriched ticker data
# ---------------------------------------------------------------------------

class EnrichedTickerListView(generics.ListAPIView):
    serializer_class = EnrichedTickerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['symbol', 'company_name', 'sector', 'industry', 'country']
    ordering_fields = ['symbol', 'sector', 'country', 'market_cap', 'last_updated_at']
    ordering = ['symbol']

    def get_queryset(self):
        qs = EnrichedTickerData.objects.all()
        asset_type = self.request.query_params.get('asset_type')
        sector = self.request.query_params.get('sector')
        country = self.request.query_params.get('country')
        if asset_type:
            qs = qs.filter(asset_type=asset_type.upper())
        if sector:
            qs = qs.filter(sector__icontains=sector)
        if country:
            qs = qs.filter(country__icontains=country)
        # Only return latest version per symbol
        from django.db.models import Max
        latest_versions = (
            EnrichedTickerData.objects.values('symbol')
            .annotate(max_version=Max('version'))
        )
        version_map = {row['symbol']: row['max_version'] for row in latest_versions}
        # Filter to only latest versions
        from django.db.models import Q
        q = Q()
        for sym, ver in version_map.items():
            q |= Q(symbol=sym, version=ver)
        return qs.filter(q) if version_map else qs.none()


@api_view(['GET'])
def enriched_ticker_detail(request, symbol):
    """Latest enriched data for a specific ticker."""
    obj = EnrichedTickerData.get_latest_version(symbol.upper())
    if obj is None:
        return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response(EnrichedTickerSerializer(obj).data)
