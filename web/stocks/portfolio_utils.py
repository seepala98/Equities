"""
Portfolio Utilities
===================

Holdings calculation, P&L computation, and performance tracking.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import yfinance as yf
from django.db.models import Sum, F, Q, Count

logger = logging.getLogger(__name__)


def calculate_holdings(
    portfolio, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> List[Dict]:
    """
    Calculate current holdings from transactions.

    Returns list of holdings with shares, cost basis, and current value.
    """
    from .models import Transaction

    queryset = portfolio.transactions.all()

    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    buys = list(
        queryset.filter(transaction_type__in=["BUY", "DRIP"])
        .values("symbol")
        .annotate(
            total_shares=Sum("quantity"), total_cost=Sum(F("quantity") * F("price"))
        )
    )

    sells = list(
        queryset.filter(transaction_type="SELL")
        .values("symbol")
        .annotate(
            total_shares=Sum("quantity"), total_proceeds=Sum(F("quantity") * F("price"))
        )
    )

    sells_by_symbol = {s["symbol"]: s for s in sells}

    holdings = []
    for buy in buys:
        symbol = buy["symbol"]
        bought_shares = buy["total_shares"] or Decimal("0")
        total_cost = buy["total_cost"] or Decimal("0")

        sold = sells_by_symbol.get(symbol, {})
        sold_shares = sold.get("total_shares") or Decimal("0")

        net_shares = bought_shares - sold_shares

        if net_shares > 0:
            avg_cost = total_cost / net_shares if net_shares > 0 else Decimal("0")

            dividends = queryset.filter(
                symbol=symbol, transaction_type__in=["DIV", "DRIP"]
            ).aggregate(total=Sum("amount"))
            dividend_total = abs(dividends["total"] or Decimal("0"))

            holdings.append(
                {
                    "symbol": symbol,
                    "total_shares": net_shares,
                    "avg_cost": avg_cost,
                    "total_cost": total_cost,
                    "current_price": None,
                    "current_value": None,
                    "gain_loss": None,
                    "gain_loss_pct": None,
                    "dividends_received": dividend_total,
                }
            )

    return holdings


def get_current_prices(symbols: List[str]) -> Dict[str, Decimal]:
    """Fetch current prices for symbols using yfinance."""
    prices = {}

    if not symbols:
        return prices

    try:
        tickers = yf.Tickers(" ".join([f"{s}.TO" for s in symbols]))

        for symbol in symbols:
            try:
                ticker = tickers.tickers.get(f"{symbol}.TO")
                if ticker:
                    info = ticker.info
                    current_price = info.get("currentPrice") or info.get(
                        "regularMarketPreviousClose"
                    )
                    if current_price:
                        prices[symbol] = Decimal(str(current_price))
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol}: {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")

    return prices


def enrich_holdings_with_prices(holdings: List[Dict]) -> List[Dict]:
    """Add current prices and P&L to holdings."""
    symbols = [h["symbol"] for h in holdings]
    prices = get_current_prices(symbols)

    enriched = []
    for holding in holdings:
        symbol = holding["symbol"]
        current_price = prices.get(symbol)

        if current_price:
            current_value = current_price * holding["total_shares"]
            total_cost = holding["total_cost"]
            gain_loss = current_value - total_cost
            gain_loss_pct = (
                (gain_loss / total_cost * 100) if total_cost > 0 else Decimal("0")
            )

            holding["current_price"] = current_price
            holding["current_value"] = current_value
            holding["gain_loss"] = gain_loss
            holding["gain_loss_pct"] = gain_loss_pct

        enriched.append(holding)

    return enriched


def calculate_portfolio_performance(
    portfolio, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> Dict:
    """Calculate portfolio performance over date range."""
    from .models import Transaction

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    holdings = calculate_holdings(portfolio, start_date, end_date)
    holdings = enrich_holdings_with_prices(holdings)

    total_invested = sum(float(h["total_cost"]) for h in holdings if h["total_cost"])

    total_current_value = sum(
        float(h["current_value"]) for h in holdings if h["current_value"]
    )

    total_dividends = sum(float(h["dividends_received"]) for h in holdings)

    if total_invested > 0:
        total_gain_loss = total_current_value - total_invested
        total_gain_loss_pct = (total_gain_loss / total_invested) * 100
    else:
        total_gain_loss = 0
        total_gain_loss_pct = 0

    daily_values = generate_daily_values(portfolio, start_date, end_date, holdings)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_invested": Decimal(str(round(total_invested, 2))),
        "total_current_value": Decimal(str(round(total_current_value, 2))),
        "total_gain_loss": Decimal(str(round(total_gain_loss, 2))),
        "total_gain_loss_pct": Decimal(str(round(total_gain_loss_pct, 2))),
        "total_dividends": Decimal(str(round(total_dividends, 2))),
        "holdings": holdings,
        "daily_values": daily_values,
    }


def generate_daily_values(
    portfolio, start_date: date, end_date: date, current_holdings: List[Dict]
) -> List[Dict]:
    """Generate daily portfolio values for charting."""
    from .models import Transaction

    symbols = [h["symbol"] for h in current_holdings]
    prices = get_current_prices(symbols)

    daily_values = []
    current_date = start_date

    while current_date <= end_date:
        day_transactions = portfolio.transactions.filter(date__lte=current_date)

        buys = (
            day_transactions.filter(transaction_type__in=["BUY", "DRIP"])
            .values("symbol")
            .annotate(
                total_shares=Sum("quantity"), total_cost=Sum(F("quantity") * F("price"))
            )
        )

        sells = (
            day_transactions.filter(transaction_type="SELL")
            .values("symbol")
            .annotate(total_shares=Sum("quantity"))
        )

        sells_by_symbol = {s["symbol"]: s["total_shares"] for s in sells}

        portfolio_value = Decimal("0")
        for buy in buys:
            symbol = buy["symbol"]
            bought = buy["total_shares"] or Decimal("0")
            sold = sells_by_symbol.get(symbol) or Decimal("0")
            shares = bought - sold

            if shares > 0:
                price = prices.get(symbol)
                if price:
                    portfolio_value += price * shares

        daily_values.append(
            {
                "date": current_date.isoformat(),
                "value": float(portfolio_value),
            }
        )

        current_date += timedelta(days=1)

    return daily_values


def get_portfolio_summary(portfolio) -> Dict:
    """Get quick portfolio summary."""
    from .models import Transaction

    total_invested = portfolio.transactions.filter(
        transaction_type__in=["BUY", "DRIP"]
    ).aggregate(total=Sum(F("quantity") * F("price")))

    total_dividends = portfolio.transactions.filter(
        transaction_type__in=["DIV", "DRIP"]
    ).aggregate(total=Sum("amount"))

    holdings = calculate_holdings(portfolio)
    holdings = enrich_holdings_with_prices(holdings)

    symbols = (
        portfolio.transactions.exclude(symbol__isnull=True)
        .values_list("symbol", flat=True)
        .distinct()
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "account_type": portfolio.account_type,
        "holdings_count": len(holdings),
        "unique_symbols": len(symbols),
        "total_invested": float(total_invested["total"] or 0),
        "total_dividends": float(abs(total_dividends["total"] or 0)),
    }


def get_heatmap_data(portfolio) -> List[Dict]:
    """Get data formatted for treemap heatmap."""
    holdings = calculate_holdings(portfolio)
    holdings = enrich_holdings_with_prices(holdings)

    heatmap_data = []
    for h in holdings:
        if h.get("gain_loss_pct") is not None:
            heatmap_data.append(
                {
                    "symbol": h["symbol"],
                    "value": float(h["current_value"] or 0),
                    "gain_loss_pct": float(h["gain_loss_pct"]),
                    "gain_loss": float(h["gain_loss"] or 0),
                }
            )

    return heatmap_data


def calculate_date_range(preset: str, start_date: str = None, end_date: str = None):
    """Calculate start and end dates based on preset or explicit dates."""
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta

    if start_date and end_date:
        return start_date, end_date

    today = date.today()

    presets = {
        "1d": today - timedelta(days=1),
        "1w": today - timedelta(weeks=1),
        "1m": today - relativedelta(months=1),
        "3m": today - relativedelta(months=3),
        "6m": today - relativedelta(months=6),
        "ytd": date(today.year, 1, 1),
        "1y": today - relativedelta(years=1),
        "5y": today - relativedelta(years=5),
        "all": date(2000, 1, 1),
    }

    if preset and preset in presets:
        return presets[preset].isoformat(), today.isoformat()

    # Default to last 30 days
    return (today - timedelta(days=30)).isoformat(), today.isoformat()


def get_dynamic_heatmap_data(portfolio, start_date=None, end_date=None, preset=None):
    """Get heatmap data with custom date range using historical price data."""
    from decimal import Decimal
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta

    from .models import HistoricalPrice, Transaction, PortfolioHolding
    from .views import fetch_prices_for_symbols

    # Calculate actual date range
    start_dt, end_dt = calculate_date_range(preset, start_date, end_date)
    start_date_obj = date.fromisoformat(start_dt)
    end_date_obj = date.fromisoformat(end_dt)

    # Get holdings and their transactions for this portfolio
    holdings = calculate_holdings(portfolio)

    # Get unique symbols
    symbols = [h["symbol"] for h in holdings if h.get("symbol")]

    # Get historical prices for the date range
    prices_qs = HistoricalPrice.objects.filter(
        symbol__in=symbols,
        date__gte=start_date_obj,
        date__lte=end_date_obj,
    ).order_by("symbol", "date")

    # Build price lookup
    price_lookup = {}
    for p in prices_qs:
        if p.symbol not in price_lookup:
            price_lookup[p.symbol] = {}
        price_lookup[p.symbol][p.date.isoformat()] = float(p.close_price)

    heatmap_data = []
    for h in holdings:
        symbol = h.get("symbol")
        if not symbol:
            continue

        quantity = float(h.get("quantity", 0))
        if quantity <= 0:
            continue

        # Get start price (first available in range)
        start_price = None
        for d in range((end_date_obj - start_date_obj).days + 1):
            check_date = (start_date_obj + timedelta(days=d)).isoformat()
            if symbol in price_lookup and check_date in price_lookup[symbol]:
                start_price = price_lookup[symbol][check_date]
                break

        # Get end price (last available in range)
        end_price = None
        for d in range((end_date_obj - start_date_obj).days + 1):
            check_date = (end_date_obj - timedelta(days=d)).isoformat()
            if symbol in price_lookup and check_date in price_lookup[symbol]:
                end_price = price_lookup[symbol][check_date]
                break

        if start_price and end_price:
            start_value = start_price * quantity
            end_value = end_price * quantity
            gain_loss = end_value - start_value
            gain_loss_pct = (gain_loss / start_value * 100) if start_value > 0 else 0

            heatmap_data.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "start_price": start_price,
                    "end_price": end_price,
                    "start_value": start_value,
                    "current_value": end_value,
                    "gain_loss": gain_loss,
                    "gain_loss_pct": gain_loss_pct,
                }
            )

    return heatmap_data


def get_heatmap_summary(portfolio, start_date=None, end_date=None, preset=None):
    """Get summary statistics for heatmap."""
    heatmap_data = get_dynamic_heatmap_data(portfolio, start_date, end_date, preset)

    if not heatmap_data:
        return {
            "total_return": 0,
            "total_return_pct": 0,
            "best_symbol": None,
            "best_return_pct": 0,
            "worst_symbol": None,
            "worst_return_pct": 0,
            "average_return_pct": 0,
            "stock_count": 0,
        }

    total_start_value = sum(h["start_value"] for h in heatmap_data)
    total_end_value = sum(h["current_value"] for h in heatmap_data)
    total_return = total_end_value - total_start_value
    total_return_pct = (
        (total_return / total_start_value * 100) if total_start_value > 0 else 0
    )

    best = max(heatmap_data, key=lambda h: h["gain_loss_pct"])
    worst = min(heatmap_data, key=lambda h: h["gain_loss_pct"])
    avg_return_pct = sum(h["gain_loss_pct"] for h in heatmap_data) / len(heatmap_data)

    return {
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "best_symbol": best["symbol"],
        "best_return_pct": best["gain_loss_pct"],
        "worst_symbol": worst["symbol"],
        "worst_return_pct": worst["gain_loss_pct"],
        "average_return_pct": avg_return_pct,
        "stock_count": len(heatmap_data),
    }


def get_historical_prices(symbol, start_date=None, end_date=None, price_type="daily"):
    """Get historical price data for a symbol."""
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta

    from .models import HistoricalPrice, IntradayPrice

    today = date.today()

    if not end_date:
        end_date = today.isoformat()
    if not start_date:
        start_date = (today - relativedelta(months=1)).isoformat()

    end_date_obj = (
        date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    )
    start_date_obj = (
        date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    )

    if price_type == "intraday":
        # Get intraday data
        prices = IntradayPrice.objects.filter(
            symbol=symbol,
            timestamp__gte=start_date_obj,
            timestamp__lte=end_date_obj,
            interval="15m",
        ).order_by("timestamp")

        return [
            {
                "timestamp": p.timestamp.isoformat(),
                "open": float(p.open_price) if p.open_price else None,
                "high": float(p.high_price) if p.high_price else None,
                "low": float(p.low_price) if p.low_price else None,
                "close": float(p.close_price) if p.close_price else None,
                "volume": p.volume,
            }
            for p in prices
        ]
    else:
        # Get daily data
        prices = HistoricalPrice.objects.filter(
            symbol=symbol,
            date__gte=start_date_obj,
            date__lte=end_date_obj,
        ).order_by("date")

        return [
            {
                "date": p.date.isoformat(),
                "open": float(p.open_price) if p.open_price else None,
                "high": float(p.high_price) if p.high_price else None,
                "low": float(p.low_price) if p.low_price else None,
                "close": float(p.close_price) if p.close_price else None,
                "adj_close": float(p.adj_close) if p.adj_close else None,
                "volume": p.volume,
            }
            for p in prices
        ]
