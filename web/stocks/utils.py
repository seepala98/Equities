from decimal import Decimal
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

from .models import Stock


def fetch_and_save(symbol: str, for_date: str = None) -> Stock:
    """Fetch OHLCV for `symbol` using yfinance and save a Stock record.

    If `for_date` (YYYY-MM-DD) is provided, fetch that trading day (yfinance will return the nearest available).
    """
    symbol = (symbol or '').upper().strip()
    if not symbol:
        raise ValueError('symbol is required')

    ticker = yf.Ticker(symbol)

    if for_date:
        # fetch single day range
        start = for_date
        end_dt = datetime.strptime(for_date, "%Y-%m-%d") + timedelta(days=1)
        end = end_dt.strftime("%Y-%m-%d")
        df = ticker.history(start=start, end=end)
    else:
        df = ticker.history(period='5d')

    if df is None or df.empty:
        raise ValueError(f'No data for {symbol} (date={for_date})')

    row = df.iloc[-1]
    # row name is a Timestamp
    row_date = row.name.date() if hasattr(row.name, 'date') else None

    def to_decimal(v):
        if pd.isna(v):
            return None
        return Decimal(str(v))

    rec = Stock.objects.create(
        symbol=symbol,
        date=row_date,
        open_price=to_decimal(row.get('Open')),
        high_price=to_decimal(row.get('High')),
        low_price=to_decimal(row.get('Low')),
        close_price=to_decimal(row.get('Close')),
        volume=int(row['Volume']) if 'Volume' in row and not pd.isna(row['Volume']) else None,
        source_url=f'yfinance://{symbol}',
    )

    return rec
