from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from .models import Stock, Listing, ETFInfo, ETFHolding
from .factories import (
    StockFactory, ListingFactory, ETFListingFactory,
    ETFInfoFactory, ETFHoldingFactory, SectorFactory,
)
from .asset_classifier import AssetClassifier
from .serializers import StockSerializer, ListingSerializer, ETFInfoSerializer


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
