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
            sold = sells_by_symbol.get(symbol, Decimal("0"))
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
