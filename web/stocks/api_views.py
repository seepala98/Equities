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
    Stock,
    Listing,
    DelistedListing,
    ETFInfo,
    ETFHolding,
    Sector,
    GeographicRegion,
    EnrichedTickerData,
    Portfolio,
    Transaction,
    PortfolioHolding,
    PortfolioCashSummary,
)
from .serializers import (
    StockSerializer,
    ListingSerializer,
    DelistedListingSerializer,
    ETFInfoSerializer,
    ETFDetailSerializer,
    ETFHoldingSerializer,
    SectorSerializer,
    GeographicRegionSerializer,
    EnrichedTickerSerializer,
    ETFPerformanceSerializer,
    PortfolioSerializer,
    TransactionSerializer,
    ParseResultSerializer,
    HoldingSerializer,
    PerformanceSerializer,
)
from .etf_utils import calculate_investment_performance, get_popular_canadian_etfs
from .etf_holdings_utils import fetch_and_store_etf

# ---------------------------------------------------------------------------
# Stocks
# ---------------------------------------------------------------------------


class StockListView(generics.ListAPIView):
    serializer_class = StockSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol"]
    ordering_fields = ["symbol", "date", "close_price", "scraped_at"]
    ordering = ["-scraped_at"]

    def get_queryset(self):
        qs = Stock.objects.all()
        symbol = self.request.query_params.get("symbol")
        if symbol:
            qs = qs.filter(symbol=symbol.upper())
        return qs


@api_view(["GET"])
def stock_latest(request, symbol):
    """Return latest price record for a symbol."""
    item = Stock.objects.filter(symbol=symbol.upper()).order_by("-scraped_at").first()
    if not item:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(StockSerializer(item).data)


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


class ListingListView(generics.ListAPIView):
    serializer_class = ListingSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol", "name"]
    ordering_fields = ["symbol", "name", "exchange", "asset_type"]
    ordering = ["exchange", "symbol"]

    def get_queryset(self):
        qs = Listing.objects.only(
            "id",
            "exchange",
            "symbol",
            "name",
            "asset_type",
            "status",
            "active",
            "status_date",
            "scraped_at",
        )
        exchange = self.request.query_params.get("exchange")
        asset_type = self.request.query_params.get("asset_type")
        active = self.request.query_params.get("active")
        if exchange:
            qs = qs.filter(exchange=exchange.upper())
        if asset_type:
            qs = qs.filter(asset_type=asset_type.upper())
        if active is not None:
            qs = qs.filter(active=active.lower() in ("1", "true", "yes"))
        return qs


class DelistedListingListView(generics.ListAPIView):
    serializer_class = DelistedListingSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol", "name"]
    ordering = ["-delisted_date"]

    def get_queryset(self):
        qs = DelistedListing.objects.all()
        exchange = self.request.query_params.get("exchange")
        if exchange:
            qs = qs.filter(exchange=exchange.upper())
        return qs


# ---------------------------------------------------------------------------
# Asset type summary
# ---------------------------------------------------------------------------


@api_view(["GET"])
def asset_type_summary(request):
    """Aggregated count of listings by asset type and exchange."""
    cache_key = "api:asset_type_summary"
    data = cache.get(cache_key)
    if data is None:
        data = list(
            Listing.objects.values("exchange", "asset_type")
            .annotate(count=Count("id"))
            .order_by("exchange", "-count")
        )
        cache.set(cache_key, data, timeout=600)  # 10 minutes
    return Response(data)


# ---------------------------------------------------------------------------
# ETFs
# ---------------------------------------------------------------------------


class ETFListView(generics.ListAPIView):
    serializer_class = ETFInfoSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol", "name", "fund_family", "category"]
    ordering_fields = ["symbol", "assets_under_management", "expense_ratio"]
    ordering = ["symbol"]
    queryset = ETFInfo.objects.all()


class ETFDetailView(generics.RetrieveAPIView):
    serializer_class = ETFDetailSerializer
    lookup_field = "symbol"
    lookup_url_kwarg = "symbol"

    def get_object(self):
        symbol = self.kwargs["symbol"].upper()
        cache_key = f"api:etf_detail:{symbol}"
        # Cache the queryset result, not the serialized data, so we can still serialize fresh
        qs = ETFInfo.objects.filter(symbol=symbol).prefetch_related(
            Prefetch(
                "holdings",
                queryset=ETFHolding.objects.select_related("stock_listing").order_by(
                    "-weight_percentage"
                ),
            ),
            "sector_allocations__sector",
            "geographic_allocations__region",
        )
        obj = qs.first()
        if obj is None:
            from rest_framework.exceptions import NotFound

            raise NotFound(f"ETF {symbol} not found.")
        return obj


class ETFHoldingsView(generics.ListAPIView):
    serializer_class = ETFHoldingSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["weight_percentage", "as_of_date"]
    ordering = ["-weight_percentage"]

    def get_queryset(self):
        symbol = self.kwargs["symbol"].upper()
        return (
            ETFHolding.objects.filter(etf__symbol=symbol)
            .select_related("stock_listing")
            .order_by("-weight_percentage")
        )


@api_view(["POST"])
def etf_fetch(request, symbol):
    """Trigger a fresh fetch of ETF data from yfinance and store it."""
    result = fetch_and_store_etf(symbol.upper())
    status_code = (
        status.HTTP_200_OK if result["success"] else status.HTTP_502_BAD_GATEWAY
    )
    return Response(result, status=status_code)


# ---------------------------------------------------------------------------
# ETF Performance
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
def etf_performance(request):
    """
    Calculate investment performance for an ETF.
    GET  ?symbol=XGRO&investment_amount=10000&start_date=2020-01-01
    POST { symbol, investment_amount, start_date, end_date }
    """
    params = request.query_params if request.method == "GET" else request.data
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
                symbol=data["symbol"],
                investment_amount=data["investment_amount"],
                start_date=str(data["start_date"]),
                end_date=str(data["end_date"]) if data.get("end_date") else None,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        cache.set(cache_key, result, timeout=3600)  # 1 hour

    return Response(result)


@api_view(["GET"])
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
    search_fields = ["sector_name"]


class GeographicRegionListView(generics.ListAPIView):
    serializer_class = GeographicRegionSerializer
    queryset = GeographicRegion.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["region_name", "country_name"]


# ---------------------------------------------------------------------------
# Enriched ticker data
# ---------------------------------------------------------------------------


class EnrichedTickerListView(generics.ListAPIView):
    serializer_class = EnrichedTickerSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol", "company_name", "sector", "industry", "country"]
    ordering_fields = ["symbol", "sector", "country", "market_cap", "last_updated_at"]
    ordering = ["symbol"]

    def get_queryset(self):
        qs = EnrichedTickerData.objects.all()
        asset_type = self.request.query_params.get("asset_type")
        sector = self.request.query_params.get("sector")
        country = self.request.query_params.get("country")
        if asset_type:
            qs = qs.filter(asset_type=asset_type.upper())
        if sector:
            qs = qs.filter(sector__icontains=sector)
        if country:
            qs = qs.filter(country__icontains=country)
        # Only return latest version per symbol
        from django.db.models import Max

        latest_versions = EnrichedTickerData.objects.values("symbol").annotate(
            max_version=Max("version")
        )
        version_map = {row["symbol"]: row["max_version"] for row in latest_versions}
        # Filter to only latest versions
        from django.db.models import Q

        q = Q()
        for sym, ver in version_map.items():
            q |= Q(symbol=sym, version=ver)
        return qs.filter(q) if version_map else qs.none()


@api_view(["GET"])
def enriched_ticker_detail(request, symbol):
    """Latest enriched data for a specific ticker."""
    obj = EnrichedTickerData.get_latest_version(symbol.upper())
    if obj is None:
        return Response({"error": "not found"}, status=status.HTTP_404_NOT_FOUND)
    return Response(EnrichedTickerSerializer(obj).data)


# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------


class PortfolioListView(generics.ListCreateAPIView):
    serializer_class = PortfolioSerializer
    queryset = Portfolio.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "account_type", "account_number"]


class PortfolioDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PortfolioSerializer
    queryset = Portfolio.objects.all()


class PortfolioTransactionsView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["symbol", "description"]
    ordering = ["-date"]

    def get_queryset(self):
        portfolio_id = self.kwargs["pk"]
        return Transaction.objects.filter(portfolio_id=portfolio_id)


@api_view(["POST"])
def parse_portfolio_file(request):
    """Parse uploaded file and return preview data without saving."""
    file = request.FILES.get("file")
    if not file:
        return Response(
            {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
        )

    content = file.read()
    filename = file.name.lower()

    if filename.endswith(".csv"):
        from .portfolio_parser import AccountStatementParser

        parser = AccountStatementParser()
        try:
            result = parser.parse_csv_content(content.decode("utf-8"))
        except Exception as e:
            result = {"error": str(e), "transactions": [], "summary": {}}
    elif filename.endswith(".pdf"):
        from .pdf_parser import PDFStatementParser

        parser = PDFStatementParser()
        try:
            result = parser.parse_pdf_content(content)
        except Exception as e:
            result = {"error": str(e), "transactions": [], "summary": {}}
    else:
        return Response(
            {"error": "Unsupported file type. Use CSV or PDF."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if "error" in result:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    serializer = ParseResultSerializer(result)
    return Response(serializer.data)


@api_view(["POST"])
def parse_portfolio_multiple(request):
    """Parse multiple uploaded files (PDF + CSV) and merge results."""
    files = request.FILES

    csv_transactions = []
    pdf_transactions = []
    holdings = []
    cash_summary = {}
    stock_lending = []
    detected_account_type = None
    detected_account_number = None
    statement_period = ""
    errors = []

    for key in files:
        file = files[key]
        content = file.read()
        filename = file.name.lower()

        if filename.endswith(".csv"):
            from .portfolio_parser import AccountStatementParser

            parser = AccountStatementParser()
            try:
                result = parser.parse_csv_content(content.decode("utf-8"))
                csv_transactions.extend(result.get("transactions", []))
                if not detected_account_type and result.get("detected_account_type"):
                    detected_account_type = result.get("detected_account_type")
                if not detected_account_number and result.get(
                    "detected_account_number"
                ):
                    detected_account_number = result.get("detected_account_number")
                if not statement_period and result.get("statement_period"):
                    statement_period = result.get("statement_period")
            except Exception as e:
                errors.append(f"CSV error: {str(e)}")

        elif filename.endswith(".pdf"):
            from .pdf_parser import PDFStatementParser

            parser = PDFStatementParser()
            try:
                result = parser.parse_pdf_content(content)
                # Get holdings/cash/stock lending from PDF
                if result.get("holdings"):
                    holdings = result.get("holdings", [])
                if result.get("cash_summary") and not cash_summary:
                    cash_summary = result.get("cash_summary", {})
                if result.get("stock_lending"):
                    stock_lending = result.get("stock_lending", [])
                if not detected_account_type and result.get("detected_account_type"):
                    detected_account_type = result.get("detected_account_type")
                if not detected_account_number and result.get(
                    "detected_account_number"
                ):
                    detected_account_number = result.get("detected_account_number")
                if not statement_period and result.get("statement_period"):
                    statement_period = result.get("statement_period")
                # Only use PDF transactions if no CSV provided
                if not csv_transactions:
                    pdf_transactions.extend(result.get("transactions", []))
            except Exception as e:
                errors.append(f"PDF error: {str(e)}")

    # Use CSV transactions if available, otherwise PDF
    all_transactions = csv_transactions if csv_transactions else pdf_transactions

    # Build summary
    summary = {
        "total_transactions": len(all_transactions),
        "buys": len(
            [t for t in all_transactions if t.get("transaction_type") == "BUY"]
        ),
        "sells": len(
            [t for t in all_transactions if t.get("transaction_type") == "SELL"]
        ),
        "dividends": len(
            [t for t in all_transactions if t.get("transaction_type") == "DIV"]
        ),
        "drips": len(
            [t for t in all_transactions if t.get("transaction_type") == "DRIP"]
        ),
        "contributions": len(
            [t for t in all_transactions if t.get("transaction_type") == "CONT"]
        ),
    }

    result = {
        "detected_account_type": detected_account_type,
        "detected_account_number": detected_account_number,
        "statement_period": statement_period,
        "transactions": all_transactions,
        "summary": summary,
        "holdings": holdings,
        "cash_summary": cash_summary,
        "stock_lending": stock_lending,
        "errors": errors,
    }

    serializer = ParseResultSerializer(result)
    return Response(serializer.data)


@api_view(["POST"])
def import_portfolio_transactions(request):
    """Import parsed transactions into a portfolio."""
    portfolio_id = request.data.get("portfolio_id")
    transactions_data = request.data.get("transactions", [])
    account_type = request.data.get("account_type")
    account_number = request.data.get("account_number")
    statement_period = request.data.get("statement_period", "")
    source_file = request.data.get("source_file", "")

    if not portfolio_id:
        return Response(
            {"error": "portfolio_id required"}, status=status.HTTP_400_BAD_REQUEST
        )

    if not transactions_data:
        return Response(
            {"error": "No transactions to import"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        portfolio = Portfolio.objects.get(id=portfolio_id)
    except Portfolio.DoesNotExist:
        return Response(
            {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
        )

    if account_type:
        portfolio.account_type = account_type
    if account_number:
        portfolio.account_number = account_number
    portfolio.save()

    imported_count = 0
    for tx_data in transactions_data:
        symbol = tx_data.get("symbol", "").upper() if tx_data.get("symbol") else ""
        tx_type = tx_data.get("transaction_type", "OTHER")
        
        # Check if transaction already exists to avoid duplicates
        exists = Transaction.objects.filter(
            portfolio=portfolio,
            symbol=symbol,
            transaction_type=tx_type,
            date=tx_data.get("date"),
            quantity=tx_data.get("quantity"),
            amount=tx_data.get("amount", 0)
        ).exists()
        
        if not exists:
            Transaction.objects.create(
                portfolio=portfolio,
                symbol=symbol,
                transaction_type=tx_type,
                date=tx_data.get("date"),
                execution_date=tx_data.get("execution_date"),
                quantity=tx_data.get("quantity"),
                price=tx_data.get("price"),
                amount=tx_data.get("amount", 0),
                balance=tx_data.get("balance"),
                currency=tx_data.get("currency", "CAD"),
                description=tx_data.get("description", ""),
                is_drip=tx_data.get("is_drip", False),
                statement_period=statement_period,
                source_file=source_file,
            )
            imported_count += 1

    return Response(
        {
            "success": True,
            "imported_count": imported_count,
            "portfolio_id": portfolio_id,
        }
    )


@api_view(["POST"])
def create_portfolio_with_import(request):
    """Create portfolio and import transactions in one step."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        name = request.data.get("name")
        account_type = request.data.get("account_type")
        account_number = request.data.get("account_number", "")
        transactions_data = request.data.get("transactions", [])
        holdings_data = request.data.get("holdings", [])
        cash_summary_data = request.data.get("cash_summary", {})
        source_file = request.data.get("source_file", "")
        statement_period = request.data.get("statement_period", "")

        logger.error(
            f"Creating portfolio: name={name}, type={account_type}, transactions={len(transactions_data)}"
        )

        if not name or not account_type:
            return Response(
                {"error": "name and account_type required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query_params = {"account_type": account_type}
        if account_number:
            query_params["account_number"] = account_number
            
        portfolio = Portfolio.objects.filter(**query_params).first()
        if not portfolio:
            portfolio = Portfolio.objects.create(
                name=name,
                account_type=account_type,
                account_number=account_number,
                institution="Wealthsimple",
            )

        imported_count = 0
        for tx_data in transactions_data:
            symbol = tx_data.get("symbol", "").upper() if tx_data.get("symbol") else ""
            tx_type = tx_data.get("transaction_type", "OTHER")
            
            exists = Transaction.objects.filter(
                portfolio=portfolio,
                symbol=symbol,
                transaction_type=tx_type,
                date=tx_data.get("date"),
                quantity=tx_data.get("quantity"),
                amount=tx_data.get("amount", 0)
            ).exists()
            
            if not exists:
                Transaction.objects.create(
                    portfolio=portfolio,
                    symbol=symbol,
                    transaction_type=tx_type,
                    date=tx_data.get("date"),
                    execution_date=tx_data.get("execution_date"),
                    quantity=tx_data.get("quantity"),
                    price=tx_data.get("price"),
                    amount=tx_data.get("amount", 0),
                    balance=tx_data.get("balance"),
                    currency=tx_data.get("currency", "CAD"),
                    description=tx_data.get("description", ""),
                    is_drip=tx_data.get("is_drip", False),
                    statement_period=statement_period,
                    source_file=source_file,
                )
                imported_count += 1

        holdings_count = 0
        for holding in holdings_data:
            PortfolioHolding.objects.update_or_create(
                portfolio=portfolio,
                symbol=holding.get("symbol", "").upper() if holding.get("symbol") else "",
                statement_period=statement_period,
                defaults={
                    "name": holding.get("name", ""),
                    "quantity": holding.get("quantity", 0),
                    "segregated_quantity": holding.get("segregated_quantity"),
                    "market_price": holding.get("price"),
                    "market_value": holding.get("market_value", 0),
                    "book_cost": holding.get("book_cost", 0),
                }
            )
            holdings_count += 1

        cash_count = 0
        if cash_summary_data:
            PortfolioCashSummary.objects.update_or_create(
                portfolio=portfolio,
                statement_period=statement_period,
                defaults={
                    "last_statement_cash_balance": cash_summary_data.get("last_statement_cash_balance", 0),
                    "total_cash_paid_in": cash_summary_data.get("total_cash_paid_in", 0),
                    "total_cash_paid_out": cash_summary_data.get("total_cash_paid_out", 0),
                    "closing_cash_balance": cash_summary_data.get("closing_cash_balance", 0),
                    "contributions_ytd": cash_summary_data.get("contributions_ytd", 0),
                }
            )
            cash_count = 1

        return Response(
            {
                "success": True,
                "imported_count": imported_count,
                "holdings_count": holdings_count,
                "cash_count": cash_count,
                "portfolio": PortfolioSerializer(portfolio).data,
            }
        )
    except Exception as e:
        logger.error(f"Error creating portfolio: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def portfolio_holdings(request, pk):
    """Get current holdings for a portfolio."""
    try:
        portfolio = Portfolio.objects.get(id=pk)
    except Portfolio.DoesNotExist:
        return Response(
            {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
        )

    from .portfolio_utils import calculate_holdings, enrich_holdings_with_prices

    holdings = calculate_holdings(portfolio)
    holdings = enrich_holdings_with_prices(holdings)

    return Response(holdings)


@api_view(["GET"])
def portfolio_performance(request, pk):
    """Get portfolio performance over date range."""
    try:
        portfolio = Portfolio.objects.get(id=pk)
    except Portfolio.DoesNotExist:
        return Response(
            {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
        )

    from datetime import date, timedelta
    from .portfolio_utils import calculate_portfolio_performance

    start_date = request.query_params.get("start_date")
    end_date = request.query_params.get("end_date")

    if not start_date:
        start_date = date.today() - timedelta(days=365)  # Default to 1 year
    else:
        start_date = date.fromisoformat(start_date)

    if end_date:
        end_date = date.fromisoformat(end_date)
    else:
        end_date = date.today()

    performance = calculate_portfolio_performance(portfolio, start_date, end_date)
    serializer = PerformanceSerializer(performance)
    return Response(serializer.data)


@api_view(["GET"])
def portfolio_heatmap(request, pk):
    """Get heatmap data for portfolio."""
    try:
        portfolio = Portfolio.objects.get(id=pk)
    except Portfolio.DoesNotExist:
        return Response(
            {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
        )

    from .portfolio_utils import get_heatmap_data

    heatmap_data = get_heatmap_data(portfolio)

    return Response(heatmap_data)


@api_view(["GET"])
def portfolio_date_range(request, pk):
    """Get the min/max transaction dates for a portfolio."""
    try:
        portfolio = Portfolio.objects.get(id=pk)
    except Portfolio.DoesNotExist:
        return Response(
            {"error": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND
        )

    from django.db.models import Min, Max

    dates = Transaction.objects.filter(portfolio=portfolio).aggregate(
        min_date=Min("date"), max_date=Max("date")
    )

    return Response(dates)
