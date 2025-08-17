from django.test import TestCase
from .models import Stock


class StockModelTest(TestCase):
    def test_create_stock(self):
        s = Stock.objects.create(symbol='TEST', close_price=1)
        self.assertEqual(str(s), 'TEST ')
