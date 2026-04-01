import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
from .models import Stock, Listing, ETFInfo, ETFHolding, Sector, GeographicRegion


class StockFactory(DjangoModelFactory):
    class Meta:
        model = Stock

    symbol = factory.Sequence(lambda n: f'SYM{n}')
    date = factory.LazyFunction(lambda: timezone.now().date())
    open_price = factory.Faker('pydecimal', left_digits=4, right_digits=4, positive=True)
    high_price = factory.Faker('pydecimal', left_digits=4, right_digits=4, positive=True)
    low_price = factory.Faker('pydecimal', left_digits=4, right_digits=4, positive=True)
    close_price = factory.Faker('pydecimal', left_digits=4, right_digits=4, positive=True)
    volume = factory.Faker('random_int', min=1000, max=10_000_000)
    source_url = factory.LazyAttribute(lambda o: f'yfinance://{o.symbol}')


class ListingFactory(DjangoModelFactory):
    class Meta:
        model = Listing
        django_get_or_create = ('exchange', 'symbol')

    exchange = 'TSX'
    symbol = factory.Sequence(lambda n: f'TST{n}')
    name = factory.LazyAttribute(lambda o: f'{o.symbol} Corp')
    asset_type = 'STOCK'
    status = 'listed'
    active = True


class ETFListingFactory(ListingFactory):
    asset_type = 'ETF'
    name = factory.LazyAttribute(lambda o: f'{o.symbol} ETF Portfolio')


class SectorFactory(DjangoModelFactory):
    class Meta:
        model = Sector
        django_get_or_create = ('sector_name',)

    sector_name = factory.Sequence(lambda n: f'Sector {n}')
    sector_code = factory.Sequence(lambda n: str(n))


class GeographicRegionFactory(DjangoModelFactory):
    class Meta:
        model = GeographicRegion
        django_get_or_create = ('region_name', 'country_name')

    region_name = 'North America'
    country_name = factory.Sequence(lambda n: f'Country {n}')
    country_code = factory.Sequence(lambda n: f'C{n}')
    region_type = 'Developed'


class ETFInfoFactory(DjangoModelFactory):
    class Meta:
        model = ETFInfo
        django_get_or_create = ('symbol',)

    symbol = factory.Sequence(lambda n: f'ETF{n}')
    name = factory.LazyAttribute(lambda o: f'{o.symbol} Portfolio ETF')
    fund_family = 'Vanguard'
    currency = 'CAD'
    category = 'Equity'


class ETFHoldingFactory(DjangoModelFactory):
    class Meta:
        model = ETFHolding

    etf = factory.SubFactory(ETFInfoFactory)
    stock_listing = factory.SubFactory(ListingFactory)
    weight_percentage = factory.Faker('pydecimal', left_digits=2, right_digits=4, positive=True, max_value=10)
    as_of_date = factory.LazyFunction(lambda: timezone.now().date())
    data_source = 'yfinance'
