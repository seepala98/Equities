"""Historical and intraday price data fetching utilities using yfinance."""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal

import yfinance as yf
import pandas as pd
from django.db import transaction
from django.utils import timezone

from .models import HistoricalPrice, IntradayPrice, PortfolioHolding, Transaction

logger = logging.getLogger(__name__)


def get_portfolio_symbols():
    """Get unique symbols from all portfolio holdings and transactions."""
    holdings_symbols = set(
        PortfolioHolding.objects.values_list("symbol", flat=True).distinct()
    )
    transaction_symbols = set(
        Transaction.objects.values_list("symbol", flat=True).distinct()
    )
    return holdings_symbols | transaction_symbols


def fetch_daily_data(symbol, period="5y"):
    """Fetch daily OHLCV data from yfinance."""
    if not symbol:
        return None
    try:
        ticker_symbol = symbol
        if not symbol.endswith(".TO") and not symbol.endswith("-") and len(symbol) <= 5:
            ticker_symbol = f"{symbol}.TO"

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, auto_adjust=False)

        if df.empty:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, auto_adjust=False)

        if df.empty:
            logger.warning(f"No daily data found for {symbol}")
            return None
        return df
    except Exception as e:
        logger.error(f"Error fetching daily data for {symbol}: {e}")
        return None


def fetch_intraday_data(symbol, interval="15m"):
    """Fetch intraday data from yfinance (max 7 days for 15m interval)."""
    if not symbol:
        return None
    try:
        ticker_symbol = symbol
        if not symbol.endswith(".TO") and not symbol.endswith("-") and len(symbol) <= 5:
            ticker_symbol = f"{symbol}.TO"

        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period="7d", interval=interval, auto_adjust=False)

        if df.empty:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="7d", interval=interval, auto_adjust=False)

        if df.empty:
            logger.warning(f"No intraday data found for {symbol} ({interval})")
            return None
        return df
    except Exception as e:
        logger.error(f"Error fetching intraday data for {symbol}: {e}")
        return None


def upsert_daily_prices(symbol, df):
    """Bulk upsert daily price data into HistoricalPrice."""
    if df is None or df.empty:
        return 0

    records = []
    for idx, row in df.iterrows():
        date_val = idx.date() if hasattr(idx, "date") else idx
        records.append(
            HistoricalPrice(
                symbol=symbol,
                date=date_val,
                open_price=Decimal(str(row.get("Open"))),
                high_price=Decimal(str(row.get("High"))),
                low_price=Decimal(str(row.get("Low"))),
                close_price=Decimal(str(row.get("Close"))),
                adj_close=Decimal(str(row.get("Adj Close", row.get("Close")))),
                volume=int(row.get("Volume", 0)),
                currency="CAD",
            )
        )

    with transaction.atomic():
        # Use bulk_create with ignore_conflicts for upsert-like behavior
        HistoricalPrice.objects.bulk_create(
            records,
            ignore_conflicts=True,
        )

    return len(records)


def upsert_intraday_prices(symbol, df, interval="15m"):
    """Bulk upsert intraday price data into IntradayPrice."""
    if df is None or df.empty:
        return 0

    import math
    import pandas as pd

    records = []
    for idx, row in df.iterrows():
        ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
        if ts.tzinfo is None:
            ts = timezone.make_aware(ts, timezone.get_current_timezone())

        def safe_decimal(value):
            if value is None:
                return None
            if pd.isna(value):
                return None
            if isinstance(value, float) and math.isnan(value):
                return None
            try:
                return Decimal(str(value))
            except:
                return None

        records.append(
            IntradayPrice(
                symbol=symbol,
                timestamp=ts,
                open_price=safe_decimal(row.get("Open")),
                high_price=safe_decimal(row.get("High")),
                low_price=safe_decimal(row.get("Low")),
                close_price=safe_decimal(row.get("Close")),
                volume=int(row.get("Volume", 0)) if row.get("Volume") else None,
                interval=interval,
            )
        )

    with transaction.atomic():
        IntradayPrice.objects.bulk_create(
            records,
            ignore_conflicts=True,
        )

    return len(records)


def get_last_fetched_date(symbol):
    """Get the most recent date for which we have daily data."""
    last = (
        HistoricalPrice.objects.filter(symbol=symbol)
        .order_by("-date")
        .values_list("date", flat=True)
        .first()
    )
    return last


def load_historical_for_all_symbols(years=5):
    """Initial bulk load of historical data for all portfolio symbols."""
    symbols = get_portfolio_symbols()
    period = f"{years}y"
    results = {"success": [], "failed": [], "total_records": 0}

    for symbol in symbols:
        logger.info(f"Fetching {period} daily data for {symbol}")
        df = fetch_daily_data(symbol, period=period)
        if df is not None:
            count = upsert_daily_prices(symbol, df)
            results["success"].append(symbol)
            results["total_records"] += count
            logger.info(f"  -> {count} records for {symbol}")
        else:
            results["failed"].append(symbol)
            logger.warning(f"  -> Failed for {symbol}")

    return results


def update_incremental_daily():
    """Fetch only new daily data since last fetch for all symbols."""
    symbols = get_portfolio_symbols()
    results = {"success": [], "failed": [], "total_records": 0}

    for symbol in symbols:
        last_date = get_last_fetched_date(symbol)

        if last_date is None:
            # No data yet, do full 5-year load
            logger.info(f"No data for {symbol}, fetching 5 years")
            df = fetch_daily_data(symbol, period="5y")
        else:
            # Fetch from day after last date
            start_date = last_date + timedelta(days=1)
            end_date = date.today()
            if start_date > end_date:
                logger.info(f"{symbol} is up to date")
                continue

            logger.info(f"Fetching incremental data for {symbol} from {start_date}")
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(
                    start=start_date.isoformat(),
                    end=(end_date + timedelta(days=1)).isoformat(),
                    auto_adjust=False,
                )
            except Exception as e:
                logger.error(f"Error fetching incremental data for {symbol}: {e}")
                results["failed"].append(symbol)
                continue

        if df is not None and not df.empty:
            count = upsert_daily_prices(symbol, df)
            results["success"].append(symbol)
            results["total_records"] += count
            logger.info(f"  -> {count} new records for {symbol}")
        else:
            results["success"].append(symbol)
            logger.info(f"  -> No new data for {symbol}")

    return results


def update_intraday_for_all_symbols(interval="15m"):
    """Fetch latest intraday data for all portfolio symbols."""
    symbols = get_portfolio_symbols()
    results = {"success": [], "failed": [], "total_records": 0}

    for symbol in symbols:
        logger.info(f"Fetching intraday data for {symbol} ({interval})")
        df = fetch_intraday_data(symbol, interval=interval)
        if df is not None:
            count = upsert_intraday_prices(symbol, df, interval=interval)
            results["success"].append(symbol)
            results["total_records"] += count
            logger.info(f"  -> {count} records for {symbol}")
        else:
            results["failed"].append(symbol)
            logger.warning(f"  -> Failed for {symbol}")

    return results
