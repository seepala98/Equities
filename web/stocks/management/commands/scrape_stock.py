from django.core.management.base import BaseCommand
from stocks.utils import fetch_and_save
from decimal import Decimal, InvalidOperation


def parse_decimal(s: str):
    if s is None:
        return None
    # remove commas and other non-numeric characters except dot and minus
    cleaned = ''.join(ch for ch in s if (ch.isdigit() or ch in '.-'))
    try:
        return Decimal(cleaned) if cleaned else None
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = 'Fetch and store OHLCV for a stock symbol (uses yfinance). Example: python manage.py scrape_stock --symbol=AAPL --date=2023-01-01'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', required=True, help='Stock symbol')
        parser.add_argument('--date', required=False, help='Date in YYYY-MM-DD to fetch (optional)')

    def handle(self, *args, **options):
        symbol = options['symbol']

        try:
            req_date = options.get('date')
            rec = fetch_and_save(symbol, for_date=req_date)
            self.stdout.write(self.style.SUCCESS(f'Stored stock for {symbol} — close={rec.close_price} volume={rec.volume} date={rec.date}'))
        except Exception as exc:
            self.stderr.write(f'Error fetching {symbol}: {exc}')
