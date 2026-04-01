from django.urls import path
from . import api_views

urlpatterns = [
    # Stocks
    path('stocks/', api_views.StockListView.as_view(), name='api-stock-list'),
    path('stocks/<str:symbol>/latest/', api_views.stock_latest, name='api-stock-latest'),

    # Listings
    path('listings/', api_views.ListingListView.as_view(), name='api-listing-list'),
    path('listings/delisted/', api_views.DelistedListingListView.as_view(), name='api-delisted-list'),
    path('listings/asset-summary/', api_views.asset_type_summary, name='api-asset-summary'),

    # ETFs
    path('etfs/', api_views.ETFListView.as_view(), name='api-etf-list'),
    path('etfs/popular/', api_views.popular_etfs, name='api-etf-popular'),
    path('etfs/performance/', api_views.etf_performance, name='api-etf-performance'),
    path('etfs/<str:symbol>/', api_views.ETFDetailView.as_view(), name='api-etf-detail'),
    path('etfs/<str:symbol>/holdings/', api_views.ETFHoldingsView.as_view(), name='api-etf-holdings'),
    path('etfs/<str:symbol>/fetch/', api_views.etf_fetch, name='api-etf-fetch'),

    # Sectors & Regions
    path('sectors/', api_views.SectorListView.as_view(), name='api-sector-list'),
    path('regions/', api_views.GeographicRegionListView.as_view(), name='api-region-list'),

    # Enriched ticker data
    path('enriched/', api_views.EnrichedTickerListView.as_view(), name='api-enriched-list'),
    path('enriched/<str:symbol>/', api_views.enriched_ticker_detail, name='api-enriched-detail'),
]
