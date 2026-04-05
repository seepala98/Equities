import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
import django

django.setup()

from stocks.models import Portfolio, Transaction, PortfolioHolding, PortfolioCashSummary
from decimal import Decimal

transactions_data = [
    {
        "date": "2026-01-02",
        "transaction_type": "BUY",
        "symbol": "EQB",
        "quantity": 0.0219,
        "price": 104.05,
        "amount": -2.28,
        "description": "Test",
        "currency": "CAD",
        "is_drip": False,
    }
]

holdings_data = [
    {
        "symbol": "EQB",
        "name": "EQB Inc",
        "quantity": 10,
        "price": 105,
        "market_value": 1050,
        "book_cost": 1000,
    }
]

cash_summary_data = {"closing_cash_balance": 100, "total_cash_paid_in": 1000}

try:
    p = Portfolio.objects.create(
        name="TEST2",
        account_type="FHSA",
        account_number="TEST456",
        institution="Wealthsimple",
    )
    print(f"Portfolio: {p.id}")

    # Create transactions
    for tx in transactions_data:
        Transaction.objects.create(
            portfolio=p,
            symbol=tx.get("symbol", "").upper() if tx.get("symbol") else "",
            transaction_type=tx.get("transaction_type", "OTHER"),
            date=tx.get("date"),
            quantity=tx.get("quantity"),
            price=tx.get("price"),
            amount=tx.get("amount", 0),
            currency=tx.get("currency", "CAD"),
            description=tx.get("description", ""),
            is_drip=tx.get("is_drip", False),
        )
    print("Transactions done")

    # Create holdings
    for h in holdings_data:
        PortfolioHolding.objects.create(
            portfolio=p,
            symbol=h.get("symbol", "").upper() if h.get("symbol") else "",
            name=h.get("name", ""),
            quantity=h.get("quantity", 0),
            market_price=h.get("price"),
            market_value=h.get("market_value", 0),
            book_cost=h.get("book_cost", 0),
        )
    print("Holdings done")

    # Create cash
    if cash_summary_data:
        PortfolioCashSummary.objects.create(
            portfolio=p,
            closing_cash_balance=cash_summary_data.get("closing_cash_balance", 0),
            total_cash_paid_in=cash_summary_data.get("total_cash_paid_in", 0),
            total_cash_paid_out=cash_summary_data.get("total_cash_paid_out", 0),
            last_statement_cash_balance=cash_summary_data.get(
                "last_statement_cash_balance", 0
            ),
            contributions_ytd=cash_summary_data.get("contributions_ytd", 0),
        )
    print("Cash done")

    print("SUCCESS!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
