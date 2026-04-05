"""
Portfolio Statement Parser
==========================

Parses CSV exports from Wealthsimple statements.
Supports TFSA and FHSA accounts with DRIP detection.
"""

import csv
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from io import StringIO


class AccountStatementParser:
    """Parse FHSA/TFSA monthly statement CSV exports."""

    TRANSACTION_TYPE_MAP = {
        "BUY": "BUY",
        "SELL": "SELL",
        "DIV": "DIV",
        "LOAN": "LOAN",
        "RECALL": "RECALL",
        "CONT": "CONT",
        "FPLINT": "INTEREST",
        "WDR": "WDR",
    }

    ACCOUNT_TYPE_PATTERNS = {
        "tax-free savings account": "TFSA",
        "tfsa": "TFSA",
        "self-directed fhsa account": "FHSA",
        "fhsa": "FHSA",
        "first home savings account": "FHSA",
    }

    ACCOUNT_NUMBER_PATTERN = re.compile(
        r"(?:account|acct|account number|acct#|acct\.?)\s*#?\s*:?\s*([A-Z0-9]{6,20})",
        re.IGNORECASE,
    )

    SYMBOL_PATTERN = re.compile(r"^([A-Z]{2,6})\s*-")
    SHARES_PATTERN = re.compile(r"(?:bought|sold)\s+([\d.]+)\s+shares?\s+at\s+\$")
    PRICE_PATTERN = re.compile(r"(?:at\s+)?\$([\d,]+\.?\d*)\s+per\s+share")
    EXEC_DATE_PATTERN = re.compile(r"\(executed\s+at\s+(\d{4}-\d{2}-\d{2})\)")

    def __init__(self):
        self.transactions: List[Dict] = []
        self.detected_account_type: Optional[str] = None
        self.detected_account_number: Optional[str] = None
        self.statement_period: str = ""
        self.errors: List[str] = []

    def parse_csv_file(self, file_path: str) -> Dict:
        """Parse CSV file and return parsed result."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_csv_content(content)

    def parse_csv_content(self, content: str) -> Dict:
        """Parse CSV content string and return parsed result."""
        self.transactions = []
        self.errors = []

        reader = csv.DictReader(StringIO(content))

        for row in reader:
            tx = self._parse_row(row)
            if tx:
                self.transactions.append(tx)

        self._detect_drip_transactions()
        self._validate_transactions()

        return self._build_result()

    def parse_dataframe(self, df) -> Dict:
        """Parse DataFrame directly."""
        self.transactions = []
        self.errors = []

        for _, row in df.iterrows():
            row_dict = {k: v for k, v in row.items() if pd.notna(v)}
            tx = self._parse_row(row_dict)
            if tx:
                self.transactions.append(tx)

        self._detect_drip_transactions()
        self._validate_transactions()

        return self._build_result()

    def _parse_row(self, row: Dict) -> Optional[Dict]:
        """Parse a single row into transaction dict."""
        date_str = row.get("date", "").strip()
        txn_type = row.get("transaction", "").strip()
        description = row.get("description", "").strip()
        amount_str = row.get("amount", "").strip()
        balance_str = row.get("balance", "").strip()
        currency = row.get("currency", "CAD").strip()

        # Fix: Sometimes CSV has symbol in currency field (e.g., "EQB" instead of "CAD")
        # Only use CAD or USD, otherwise default to CAD
        if currency not in ["CAD", "USD"]:
            currency = "CAD"

        if not date_str or not txn_type:
            return None

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self.errors.append(f"Invalid date format: {date_str}")
            return None

        try:
            amount = Decimal(amount_str) if amount_str else Decimal("0")
        except ValueError:
            amount = Decimal("0")

        try:
            balance = Decimal(balance_str) if balance_str else None
        except ValueError:
            balance = None

        transaction_type = self.TRANSACTION_TYPE_MAP.get(txn_type, txn_type)

        if transaction_type not in [
            "BUY",
            "SELL",
            "DIV",
            "CONT",
            "WDR",
            "LOAN",
            "RECALL",
            "INTEREST",
        ]:
            return None

        symbol = self._extract_symbol(description)
        shares, price = self._extract_shares_price(description)
        exec_date = self._extract_execution_date(description)

        return {
            "date": date,
            "transaction_type": transaction_type,
            "symbol": symbol,
            "quantity": shares,
            "price": price,
            "execution_date": exec_date,
            "amount": amount,
            "balance": balance,
            "currency": currency,
            "description": description,
            "is_drip": False,
            "warnings": [],
        }

    def _extract_symbol(self, description: str) -> Optional[str]:
        """Extract stock symbol from description."""
        match = self.SYMBOL_PATTERN.match(description)
        if match:
            return match.group(1)

        alt_pattern = re.search(r"^([A-Z]{2,6})\s+[-:]", description)
        if alt_pattern:
            return alt_pattern.group(1)

        return None

    def _extract_shares_price(
        self, description: str
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract shares and price from buy/sell description."""
        shares = None
        price = None

        match = re.search(
            r"(?:bought|sold)\s+([\d.]+)\s+shares?\s+at\s+\$([\d,]+\.?\d*)",
            description,
            re.IGNORECASE,
        )
        if match:
            try:
                shares = Decimal(match.group(1))
                price = Decimal(match.group(2).replace(",", ""))
            except (ValueError, IndexError):
                pass

        return shares, price

    def _extract_execution_date(self, description: str) -> Optional[datetime]:
        """Extract execution date from description."""
        match = self.EXEC_DATE_PATTERN.search(description)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
        return None

    def _detect_drip_transactions(self):
        """Detect DRIP by matching DIV to subsequent BUY for same symbol."""
        self.transactions = sorted(self.transactions, key=lambda x: x["date"])

        for i, tx in enumerate(self.transactions):
            if tx["transaction_type"] == "DIV":
                symbol = tx["symbol"]
                div_date = tx["date"]
                div_amount = abs(tx["amount"])

                for j in range(i + 1, min(i + 5, len(self.transactions))):
                    next_tx = self.transactions[j]

                    if (
                        next_tx["transaction_type"] == "BUY"
                        and next_tx["symbol"] == symbol
                        and (next_tx["date"] - div_date).days <= 5
                        and next_tx["amount"] < 0
                    ):
                        next_price = next_tx["price"]
                        if next_price and div_amount > 0:
                            expected_shares = div_amount / next_price
                            actual_shares = next_tx["quantity"]

                            if (
                                actual_shares
                                and abs(float(expected_shares) - float(actual_shares))
                                < 0.01
                            ):
                                tx["transaction_type"] = "DRIP"
                                tx["is_drip"] = True
                                next_tx["is_drip"] = True
                                tx["warnings"].append(
                                    f"DRIP detected with {symbol} on {next_tx['date']}"
                                )
                                break

    def _validate_transactions(self):
        """Validate transactions and add warnings."""
        for tx in self.transactions:
            if tx["transaction_type"] in ["BUY", "SELL"] and not tx["symbol"]:
                tx["warnings"].append("No symbol found for trade")

            # Only warn about missing price for actual BUY/SELL, not DRIP (which comes from DIV)
            if tx["transaction_type"] == "BUY" and not tx["price"]:
                tx["warnings"].append("No price found for purchase")

            if tx["transaction_type"] in ["BUY", "SELL"] and not tx["quantity"]:
                tx["warnings"].append("No quantity found for trade")

    def _build_result(self) -> Dict:
        """Build the final parsed result."""
        summary = {
            "total_transactions": len(self.transactions),
            "buys": len(
                [t for t in self.transactions if t["transaction_type"] == "BUY"]
            ),
            "sells": len(
                [t for t in self.transactions if t["transaction_type"] == "SELL"]
            ),
            "dividends": len(
                [t for t in self.transactions if t["transaction_type"] == "DIV"]
            ),
            "drips": len(
                [t for t in self.transactions if t["transaction_type"] == "DRIP"]
            ),
            "contributions": len(
                [t for t in self.transactions if t["transaction_type"] == "CONT"]
            ),
            "withdrawals": len(
                [t for t in self.transactions if t["transaction_type"] == "WDR"]
            ),
        }

        if self.transactions:
            dates = [t["date"] for t in self.transactions if t["date"]]
            if dates:
                self.statement_period = f"{dates[0].year}-{dates[0].month:02d}"

        return {
            "detected_account_type": self.detected_account_type,
            "detected_account_number": self.detected_account_number,
            "statement_period": self.statement_period,
            "transactions": self.transactions,
            "summary": summary,
            "errors": self.errors,
        }

    def detect_account_from_content(
        self, content: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Detect account type and number from CSV content."""
        content_lower = content.lower()

        for pattern, account_type in self.ACCOUNT_TYPE_PATTERNS.items():
            if pattern in content_lower:
                self.detected_account_type = account_type
                break

        match = self.ACCOUNT_NUMBER_PATTERN.search(content)
        if match:
            self.detected_account_number = match.group(1)

        return self.detected_account_type, self.detected_account_number


def parse_portfolio_file(file_path: str) -> Dict:
    """Convenience function to parse a portfolio file."""
    parser = AccountStatementParser()
    return parser.parse_csv_file(file_path)


def parse_portfolio_content(content: str) -> Dict:
    """Convenience function to parse portfolio content."""
    parser = AccountStatementParser()
    return parser.parse_csv_content(content)
