from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from datetime import date, timedelta
from django.utils import timezone

from .models import Stock, Listing, ETFInfo, ETFHolding, EnrichedTickerData, Portfolio, Transaction, VettaFiIndex
from .factories import (
    StockFactory, ListingFactory, ETFListingFactory,
    ETFInfoFactory, ETFHoldingFactory, SectorFactory,
)
from .asset_classifier import AssetClassifier
from .serializers import StockSerializer, ListingSerializer, ETFInfoSerializer, PortfolioSerializer
from .api_views import invalidate_asset_type_summary_cache


# ── Model tests ───────────────────────────────────────────────────────────────

class StockModelTest(TestCase):
    def test_create_stock(self):
        s = Stock.objects.create(symbol='TEST', close_price=1)
        self.assertEqual(str(s), 'TEST ')

    def test_factory_creates_valid_stock(self):
        stock = StockFactory(symbol='SHOP', close_price=Decimal('100.5000'))
        self.assertEqual(stock.symbol, 'SHOP')
        self.assertEqual(stock.close_price, Decimal('100.5000'))
        self.assertIsNotNone(stock.pk)

    def test_stock_ordering_by_scraped_at(self):
        s1 = StockFactory(symbol='A')
        s2 = StockFactory(symbol='B')
        latest = Stock.objects.order_by('-scraped_at').first()
        self.assertEqual(latest.pk, s2.pk)


class ListingModelTest(TestCase):
    def test_str_representation(self):
        listing = ListingFactory(exchange='TSX', symbol='SHOP', name='Shopify Inc')
        self.assertIn('SHOP', str(listing))
        self.assertIn('TSX', str(listing))

    def test_unique_together_exchange_symbol(self):
        ListingFactory(exchange='TSX', symbol='SHOP')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Listing.objects.create(exchange='TSX', symbol='SHOP', name='Duplicate')

    def test_asset_type_defaults_to_stock(self):
        listing = ListingFactory()
        self.assertEqual(listing.asset_type, 'STOCK')

    def test_etf_listing_has_etf_asset_type(self):
        etf = ETFListingFactory()
        self.assertEqual(etf.asset_type, 'ETF')


class ETFInfoModelTest(TestCase):
    def test_aum_formatted_billions(self):
        etf = ETFInfoFactory(assets_under_management=5_000_000_000)
        self.assertEqual(etf.aum_formatted, '$5.00B')

    def test_aum_formatted_millions(self):
        etf = ETFInfoFactory(assets_under_management=250_000_000)
        self.assertEqual(etf.aum_formatted, '$250.0M')

    def test_mer_formatted(self):
        etf = ETFInfoFactory(expense_ratio=Decimal('0.0020'))
        self.assertEqual(etf.mer_formatted, '0.20%')

    def test_aum_formatted_na_when_null(self):
        etf = ETFInfoFactory(assets_under_management=None)
        self.assertEqual(etf.aum_formatted, 'N/A')


# ── Asset classifier tests ────────────────────────────────────────────────────

class AssetClassifierTest(TestCase):
    def setUp(self):
        self.classifier = AssetClassifier()

    def _listing(self, name, symbol='TST', exchange='TSX'):
        return ListingFactory(symbol=symbol, name=name, exchange=exchange)

    def test_classifies_etf_by_name(self):
        listing = self._listing('iShares Core S&P 500 ETF Portfolio', 'XSP')
        result = self.classifier.classify_listing(listing)
        self.assertEqual(result, 'ETF')

    def test_classifies_reit_by_name(self):
        listing = self._listing('RioCan Real Estate Investment Trust', 'REI.UN')
        result = self.classifier.classify_listing(listing)
        self.assertEqual(result, 'REIT')

    def test_classifies_warrant_by_symbol(self):
        listing = self._listing('Some Corp Warrant', 'ABC.WT')
        result = self.classifier.classify_listing(listing)
        self.assertEqual(result, 'WARRANT')

    def test_classifies_preferred_by_symbol(self):
        listing = self._listing('Bank Preferred Share', 'BNS.PR.A')
        result = self.classifier.classify_listing(listing)
        self.assertEqual(result, 'PREFERRED')


# ── Serializer tests ──────────────────────────────────────────────────────────

class StockSerializerTest(TestCase):
    def test_serializes_stock_fields(self):
        stock = StockFactory(symbol='AAPL')
        data = StockSerializer(stock).data
        self.assertEqual(data['symbol'], 'AAPL')
        self.assertIn('close_price', data)
        self.assertIn('scraped_at', data)

    def test_serializes_listing(self):
        listing = ListingFactory(symbol='BMO', name='Bank of Montreal', exchange='TSX')
        data = ListingSerializer(listing).data
        self.assertEqual(data['symbol'], 'BMO')
        self.assertEqual(data['exchange'], 'TSX')

    def test_etf_info_serializer_includes_formatted_fields(self):
        etf = ETFInfoFactory(assets_under_management=1_000_000_000, expense_ratio=Decimal('0.0020'))
        data = ETFInfoSerializer(etf).data
        self.assertEqual(data['aum_formatted'], '$1.00B')
        self.assertEqual(data['mer_formatted'], '0.20%')


# ── View tests ────────────────────────────────────────────────────────────────

class HomeViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_returns_200(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_home_shows_latest_stocks(self):
        StockFactory(symbol='TD')
        StockFactory(symbol='RY')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'TD')

    def test_listings_view_paginated(self):
        for i in range(60):
            ListingFactory(symbol=f'S{i:03}', exchange='TSX')
        response = self.client.get(reverse('listings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Page 1')

    def test_listings_filter_by_exchange(self):
        ListingFactory(symbol='TSX1', exchange='TSX')
        ListingFactory(symbol='VEN1', exchange='TSXV')
        response = self.client.get(reverse('listings') + '?exchange=TSX')
        self.assertContains(response, 'TSX1')

    def test_latest_json_endpoint(self):
        StockFactory(symbol='SHOP', close_price=Decimal('50.00'))
        response = self.client.get(reverse('latest', kwargs={'symbol': 'SHOP'}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['symbol'], 'SHOP')
        self.assertEqual(data['close_price'], '50.0000')

    def test_latest_404_for_unknown_symbol(self):
        response = self.client.get(reverse('latest', kwargs={'symbol': 'NOPE'}))
        self.assertEqual(response.status_code, 404)


# ── API tests ─────────────────────────────────────────────────────────────────

class APIListingsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        ListingFactory(symbol='RY', exchange='TSX', asset_type='STOCK', name='Royal Bank')
        ListingFactory(symbol='XGRO', exchange='TSX', asset_type='ETF', name='iShares Growth ETF')
        ListingFactory(symbol='ACV', exchange='TSXV', asset_type='STOCK', name='ACV Auctions')

    def test_list_all_listings(self):
        response = self.client.get('/api/v1/listings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 3)

    def test_filter_by_exchange(self):
        response = self.client.get('/api/v1/listings/?exchange=TSX')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data['results']:
            self.assertEqual(item['exchange'], 'TSX')

    def test_filter_by_asset_type(self):
        response = self.client.get('/api/v1/listings/?asset_type=ETF')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data['results']:
            self.assertEqual(item['asset_type'], 'ETF')

    def test_search_by_symbol(self):
        response = self.client.get('/api/v1/listings/?search=RY')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        symbols = [r['symbol'] for r in response.data['results']]
        self.assertIn('RY', symbols)

    def test_asset_summary_endpoint(self):
        response = self.client.get('/api/v1/listings/asset-summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class APIETFTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.etf = ETFInfoFactory(
            symbol='XGRO',
            name='iShares Core Growth ETF',
            assets_under_management=2_000_000_000,
            expense_ratio=Decimal('0.0020'),
        )
        listing = ETFListingFactory(symbol='TD', exchange='TSX')
        ETFHoldingFactory(etf=self.etf, stock_listing=listing, weight_percentage=Decimal('5.25'))

    def test_etf_list(self):
        response = self.client.get('/api/v1/etfs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        symbols = [r['symbol'] for r in response.data['results']]
        self.assertIn('XGRO', symbols)

    def test_etf_detail_includes_holdings(self):
        response = self.client.get('/api/v1/etfs/XGRO/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['symbol'], 'XGRO')
        self.assertIn('holdings', response.data)
        self.assertEqual(len(response.data['holdings']), 1)

    def test_etf_holdings_endpoint(self):
        response = self.client.get('/api/v1/etfs/XGRO/holdings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['weight_percentage'], '5.2500')

    def test_etf_detail_404_for_unknown(self):
        response = self.client.get('/api/v1/etfs/UNKNOWN/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_popular_etfs_endpoint(self):
        response = self.client.get('/api/v1/etfs/popular/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('XGRO', response.data)


class APIStocksTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.stock = StockFactory(symbol='SHOP', close_price=Decimal('100.0000'))

    def test_stock_list(self):
        response = self.client.get('/api/v1/stocks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_stock_latest(self):
        response = self.client.get('/api/v1/stocks/SHOP/latest/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['symbol'], 'SHOP')

    def test_stock_latest_404(self):
        response = self.client.get('/api/v1/stocks/NOPE/latest/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ── Performance improvement tests ─────────────────────────────────────────────

class EnrichedTickerDataTest(TestCase):
    def test_get_latest_version(self):
        EnrichedTickerData.objects.create(symbol='TEST', version=1, asset_type='STOCK')
        EnrichedTickerData.objects.create(symbol='TEST', version=2, asset_type='ETF')
        latest = EnrichedTickerData.get_latest_version('TEST')
        self.assertEqual(latest.version, 2)
        self.assertEqual(latest.asset_type, 'ETF')

    def test_list_returns_only_latest_versions(self):
        client = APIClient()
        EnrichedTickerData.objects.create(symbol='A', version=1, asset_type='STOCK', sector='Tech')
        EnrichedTickerData.objects.create(symbol='A', version=2, asset_type='ETF', sector='Finance')
        EnrichedTickerData.objects.create(symbol='B', version=1, asset_type='STOCK', sector='Tech')

        response = client.get('/api/v1/enriched/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        symbols = [r['symbol'] for r in response.data['results']]
        self.assertEqual(symbols.count('A'), 1)
        result_a = [r for r in response.data['results'] if r['symbol'] == 'A'][0]
        self.assertEqual(result_a['asset_type'], 'ETF')

    def test_list_filters_by_asset_type(self):
        client = APIClient()
        EnrichedTickerData.objects.create(symbol='A', version=1, asset_type='STOCK')
        EnrichedTickerData.objects.create(symbol='B', version=1, asset_type='ETF')

        response = client.get('/api/v1/enriched/?asset_type=STOCK')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['symbol'], 'A')


class PortfolioSerializerAnnotationTest(TestCase):
    def test_portfolio_list_uses_annotations(self):
        client = APIClient()
        portfolio = Portfolio.objects.create(name='Test', account_type='TFSA')
        Transaction.objects.create(
            portfolio=portfolio, symbol='A', transaction_type='BUY',
            date=date.today(), quantity=10, price=Decimal('100'), amount=Decimal('1000')
        )
        Transaction.objects.create(
            portfolio=portfolio, symbol='B', transaction_type='BUY',
            date=date.today(), quantity=5, price=Decimal('50'), amount=Decimal('250')
        )
        Transaction.objects.create(
            portfolio=portfolio, symbol='A', transaction_type='BUY',
            date=date.today(), quantity=3, price=Decimal('100'), amount=Decimal('300')
        )

        response = client.get('/api/v1/portfolios/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        p = results[0]
        self.assertEqual(p['holdings_count'], 2)
        self.assertAlmostEqual(float(p['total_invested']), 1550.0)

    def test_portfolio_serializer_returns_integer_holdings_count(self):
        portfolio = Portfolio.objects.create(name='Test', account_type='TFSA')
        serializer = PortfolioSerializer(portfolio)
        data = serializer.data
        self.assertIsInstance(data['holdings_count'], int)
        self.assertIsInstance(data['total_invested'], float)


class ETFDetailCacheTest(TestCase):
    def test_etf_detail_caches_result(self):
        client = APIClient()
        etf = ETFInfoFactory(symbol='CACHE', name='Cache Test ETF')
        cache_key = 'api:etf_detail:CACHE'
        cache.delete(cache_key)

        response = client.get('/api/v1/etfs/CACHE/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['symbol'], 'CACHE')

        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)

    def test_etf_detail_returns_cached_result(self):
        client = APIClient()
        etf = ETFInfoFactory(symbol='CACHE2', name='Cache Test ETF 2')
        cache_key = 'api:etf_detail:CACHE2'
        cache.delete(cache_key)

        client.get('/api/v1/etfs/CACHE2/')
        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)

        etf.name = 'Updated Name'
        etf.save()

        response = client.get('/api/v1/etfs/CACHE2/')
        self.assertEqual(response.data['symbol'], 'CACHE2')


class AssetClassifierBulkUpdateTest(TestCase):
    def test_classify_all_listings_uses_bulk_update(self):
        classifier = AssetClassifier()
        for i in range(10):
            ListingFactory(symbol=f'BULK{i}', name=f'Test ETF {i} Portfolio', exchange='TSX')

        results = classifier.classify_all_listings(limit=10)
        self.assertEqual(results['total_processed'], 10)

        etf_count = Listing.objects.filter(asset_type='ETF').count()
        self.assertGreater(etf_count, 0)


class CacheInvalidationTest(TestCase):
    def test_invalidate_asset_type_summary_cache(self):
        cache.set('api:asset_type_summary', [{'test': 'data'}], timeout=600)
        self.assertIsNotNone(cache.get('api:asset_type_summary'))

        invalidate_asset_type_summary_cache()
        self.assertIsNone(cache.get('api:asset_type_summary'))


class ListingListViewOnlyFieldsTest(TestCase):
    def test_listings_endpoint_includes_listing_url(self):
        client = APIClient()
        ListingFactory(symbol='URL', exchange='TSX', listing_url='https://example.com')

        response = client.get('/api/v1/listings/?search=URL')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data['count'], 1)


class EnrichedDataServiceTest(TestCase):
    def test_get_tickers_by_asset_type_single_query(self):
        from .enriched_data_service import EnrichedDataService

        EnrichedTickerData.objects.create(symbol='SVC1', version=1, asset_type='STOCK', company_name='Stock One')
        EnrichedTickerData.objects.create(symbol='SVC1', version=2, asset_type='STOCK', company_name='Stock One Updated')
        EnrichedTickerData.objects.create(symbol='SVC2', version=1, asset_type='ETF', company_name='ETF One')

        service = EnrichedDataService()
        results = service.get_tickers_by_asset_type('STOCK', limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['symbol'], 'SVC1')
        self.assertEqual(results[0]['company_name'], 'Stock One Updated')

    def test_search_tickers_single_query(self):
        from .enriched_data_service import EnrichedDataService

        EnrichedTickerData.objects.create(symbol='SEARCH', version=1, company_name='Search Corp')
        EnrichedTickerData.objects.create(symbol='OTHER', version=1, company_name='Other Corp')

        service = EnrichedDataService()
        results = service.search_tickers('search', limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['symbol'], 'SEARCH')


# -- VettaFi Index tests --

class VettaFiIndexModelTest(TestCase):
    def test_create_index(self):
        idx = VettaFiIndex.objects.create(
            ticker='TEST',
            name='Test Index',
            category='equity_benchmark',
            region='north_america',
        )
        self.assertEqual(str(idx), 'TEST - Test Index')

    def test_factsheet_pdf_url(self):
        idx = VettaFiIndex.objects.create(
            ticker='AEDW',
            name='Alerian Midstream Energy Dividend Weighted Index',
            category='equity_benchmark',
        )
        self.assertIn('AEDW', idx.factsheet_pdf_url)
        self.assertIn('Factsheet.pdf', idx.factsheet_pdf_url)

    def test_factsheet_pdf_url_custom(self):
        idx = VettaFiIndex.objects.create(
            ticker='TEST',
            name='Test Index',
            category='equity_benchmark',
            factsheet_url='https://example.com/custom.pdf',
        )
        self.assertEqual(idx.factsheet_pdf_url, 'https://example.com/custom.pdf')

    def test_unique_ticker(self):
        VettaFiIndex.objects.create(
            ticker='UNIQUE',
            name='Unique Index',
            category='equity_benchmark',
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            VettaFiIndex.objects.create(
                ticker='UNIQUE',
                name='Duplicate Index',
                category='factor',
            )

    def test_category_choices(self):
        idx = VettaFiIndex.objects.create(
            ticker='CAT',
            name='Category Test',
            category='thematic',
            region='global',
        )
        self.assertEqual(idx.get_category_display(), 'Thematic')
        self.assertEqual(idx.get_region_display(), 'Global')


class VettaFiIndexAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        VettaFiIndex.objects.create(
            ticker='AEDW',
            name='Alerian Midstream Energy Dividend Weighted Index',
            category='equity_benchmark',
            region='north_america',
            factsheet_url='https://vettafi-docs.b-cdn.net/Factsheets/AEDW%20Factsheet.pdf',
        )
        VettaFiIndex.objects.create(
            ticker='ROBO',
            name='ROBO Global Robotics and Automation Index',
            category='thematic',
            region='global',
        )
        VettaFiIndex.objects.create(
            ticker='ACQVAL',
            name='American Century U.S. Quality Value Index',
            category='equity_benchmark',
            region='north_america',
        )

    def test_list_all_indexes(self):
        response = self.client.get('/api/v1/vettafi/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_filter_by_category(self):
        response = self.client.get('/api/v1/vettafi/?category=equity_benchmark')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_by_region(self):
        response = self.client.get('/api/v1/vettafi/?region=global')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['ticker'], 'ROBO')

    def test_search_by_ticker(self):
        response = self.client.get('/api/v1/vettafi/?search=AEDW')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_search_by_name(self):
        response = self.client.get('/api/v1/vettafi/?search=Robotics')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_detail_view(self):
        response = self.client.get('/api/v1/vettafi/AEDW/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ticker'], 'AEDW')
        self.assertEqual(response.data['category_display'], 'Equity Benchmark')

    def test_detail_not_found(self):
        response = self.client.get('/api/v1/vettafi/NONEXISTENT/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_categories_endpoint(self):
        response = self.client.get('/api/v1/vettafi/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_regions_endpoint(self):
        response = self.client.get('/api/v1/vettafi/regions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        regions = [r['region'] for r in response.data]
        self.assertIn('north_america', regions)
        self.assertIn('global', regions)

    def test_ordering(self):
        response = self.client.get('/api/v1/vettafi/?ordering=-ticker')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tickers = [r['ticker'] for r in response.data['results']]
        self.assertEqual(tickers, sorted(tickers, reverse=True))
