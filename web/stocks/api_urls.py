from django.urls import path
from . import api_views

urlpatterns = [
    # Stocks
    path("stocks/", api_views.StockListView.as_view(), name="api-stock-list"),
    path(
        "stocks/<str:symbol>/latest/", api_views.stock_latest, name="api-stock-latest"
    ),
    # Listings
    path("listings/", api_views.ListingListView.as_view(), name="api-listing-list"),
    path(
        "listings/delisted/",
        api_views.DelistedListingListView.as_view(),
        name="api-delisted-list",
    ),
    path(
        "listings/asset-summary/",
        api_views.asset_type_summary,
        name="api-asset-summary",
    ),
    # ETFs
    path("etfs/", api_views.ETFListView.as_view(), name="api-etf-list"),
    path("etfs/popular/", api_views.popular_etfs, name="api-etf-popular"),
    path("etfs/performance/", api_views.etf_performance, name="api-etf-performance"),
    path(
        "etfs/<str:symbol>/", api_views.ETFDetailView.as_view(), name="api-etf-detail"
    ),
    path(
        "etfs/<str:symbol>/holdings/",
        api_views.ETFHoldingsView.as_view(),
        name="api-etf-holdings",
    ),
    path("etfs/<str:symbol>/fetch/", api_views.etf_fetch, name="api-etf-fetch"),
    # Sectors & Regions
    path("sectors/", api_views.SectorListView.as_view(), name="api-sector-list"),
    path(
        "regions/", api_views.GeographicRegionListView.as_view(), name="api-region-list"
    ),
    # Enriched ticker data
    path(
        "enriched/",
        api_views.EnrichedTickerListView.as_view(),
        name="api-enriched-list",
    ),
    path(
        "enriched/<str:symbol>/",
        api_views.enriched_ticker_detail,
        name="api-enriched-detail",
    ),
    # Portfolios
    path(
        "portfolios/", api_views.PortfolioListView.as_view(), name="api-portfolio-list"
    ),
    path(
        "portfolios/parse/", api_views.parse_portfolio_file, name="api-portfolio-parse"
    ),
    path(
        "portfolios/parse-multiple/",
        api_views.parse_portfolio_multiple,
        name="api-portfolio-parse-multiple",
    ),
    path(
        "portfolios/import/",
        api_views.import_portfolio_transactions,
        name="api-portfolio-import",
    ),
    path(
        "portfolios/create/",
        api_views.create_portfolio_with_import,
        name="api-portfolio-create",
    ),
    path(
        "portfolios/<int:pk>/",
        api_views.PortfolioDetailView.as_view(),
        name="api-portfolio-detail",
    ),
    path(
        "portfolios/<int:pk>/transactions/",
        api_views.PortfolioTransactionsView.as_view(),
        name="api-portfolio-transactions",
    ),
    path(
        "portfolios/<int:pk>/holdings/",
        api_views.portfolio_holdings,
        name="api-portfolio-holdings",
    ),
    path(
        "portfolios/<int:pk>/performance/",
        api_views.portfolio_performance,
        name="api-portfolio-performance",
    ),
    path(
        "portfolios/<int:pk>/heatmap/",
        api_views.portfolio_heatmap,
        name="api-portfolio-heatmap",
    ),
    path(
        "portfolios/<int:pk>/heatmap-dynamic/",
        api_views.portfolio_heatmap_dynamic,
        name="api-portfolio-heatmap-dynamic",
    ),
    path(
        "portfolios/<int:pk>/heatmap-summary/",
        api_views.portfolio_heatmap_summary,
        name="api-portfolio-heatmap-summary",
    ),
    path(
        "portfolios/<int:pk>/date-range/",
        api_views.portfolio_date_range,
        name="api-portfolio-date-range",
    ),
    path(
        "historical-prices/<str:symbol>/",
        api_views.historical_prices,
        name="api-historical-prices",
    ),
]
