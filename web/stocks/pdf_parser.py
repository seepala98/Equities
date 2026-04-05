"""
PDF Portfolio Statement Parser
==============================

Parses PDF monthly statements from Wealthsimple.
Uses pdfplumber to extract tables and text.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from io import BytesIO

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

from .portfolio_parser import AccountStatementParser


class PDFStatementParser:
    """Parse PDF monthly statements using pdfplumber."""

    ACCOUNT_TYPE_PATTERNS = {
        "tax-free savings account": "TFSA",
        "tfsa": "TFSA",
        "self-directed fhsa account": "FHSA",
        "fhsa": "FHSA",
        "first home savings account": "FHSA",
    }

    ACCOUNT_NUMBER_PATTERNS = [
        re.compile(r"^([A-Z]{2}\d[A-Z0-9]{5,20})(?:\s|$)", re.MULTILINE),
        re.compile(r"^HQ([A-Z0-9]{6,20})", re.MULTILINE),
    ]

    DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

    STATEMENT_PERIOD_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})"
    )

    def __init__(self):
        self.detected_account_type: Optional[str] = None
        self.detected_account_number: Optional[str] = None
        self.statement_period: str = ""

    def parse_pdf_file(self, file_path: str) -> Dict:
        """Parse PDF file and return parsed result."""
        if not PDFPLUMBER_AVAILABLE:
            return {
                "error": "pdfplumber not installed. Install with: pip install pdfplumber",
                "transactions": [],
                "summary": {},
            }

        with pdfplumber.open(file_path) as pdf:
            return self._parse_pdf(pdf)

    def parse_pdf_content(self, content: bytes) -> Dict:
        """Parse PDF from bytes content."""
        if not PDFPLUMBER_AVAILABLE:
            return {
                "error": "pdfplumber not installed. Install with: pip install pdfplumber",
                "transactions": [],
                "summary": {},
            }

        with pdfplumber.open(BytesIO(content)) as pdf:
            return self._parse_pdf(pdf)

    def _parse_pdf(self, pdf) -> Dict:
        """Parse PDF object."""
        full_text = ""
        all_tables = []

        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

            tables = page.extract_tables()
            if tables:
                for table in tables:
                    if table:
                        all_tables.append(table)

        self._detect_account_info(full_text)

        # Extract all data sections
        holdings = self._extract_holdings_from_text(full_text)
        cash_summary = self._extract_cash_summary(full_text)
        stock_lending = self._extract_stock_lending(full_text)
        transactions = self._extract_transactions_from_text(full_text)

        if not transactions:
            transactions = self._extract_transactions_from_tables(all_tables, full_text)

        transactions = self._apply_drip_detection(transactions)

        result = self._build_result(transactions, full_text)
        result["holdings"] = holdings
        result["cash_summary"] = cash_summary
        result["stock_lending"] = stock_lending

        return result

    def _extract_stock_lending(self, text: str) -> List[Dict]:
        """Extract stock lending info from PDF."""
        stock_lending = []
        in_section = False
        for line in text.split("\n"):
            if "Stock Lending" in line:
                in_section = True
                continue
            if in_section:
                if "Activity" in line or "Participated" in line:
                    continue
                if (
                    "Collateral" in line
                    or "Market Value" in line
                    or "Symbol" in line
                    or "*" in line
                ):
                    continue
                if not line:
                    break
                # Parse: EQB $541.80 $0.00 $541.80 $0.00
                match = re.match(
                    r"^([A-Z]{2,6})\s+\$?([\d,.\-]+)\s+\$?([\d,.\-]+)\s+\$?([\d,.\-]+)\s+\$?([\d,.\-]+)",
                    line,
                )
                if match:
                    try:
                        stock_lending.append(
                            {
                                "symbol": match.group(1),
                                "collateral_cad": Decimal(
                                    match.group(2).replace(",", "")
                                ),
                                "collateral_usd": Decimal(
                                    match.group(3).replace(",", "")
                                ),
                                "loan_value_cad": Decimal(
                                    match.group(4).replace(",", "")
                                ),
                                "loan_value_usd": Decimal(
                                    match.group(5).replace(",", "")
                                ),
                            }
                        )
                    except:
                        pass
        return stock_lending

    def _extract_holdings_from_text(self, text: str) -> List[Dict]:
        """Extract holdings from Portfolio Assets section."""
        holdings = []
        in_holdings_section = False

        # Join lines to handle multi-line entries
        text = text.replace("\nCAD ", " CAD ")

        for line in text.split("\n"):
            line = line.strip()

            if "Portfolio Assets" in line or "Portfolio Equities" in line:
                in_holdings_section = True
                continue

            if in_holdings_section:
                if line.startswith("Total $") or line.startswith("Total") or not line:
                    if holdings:
                        break
                    continue

                # Try to parse holdings line - two patterns:
                # Pattern 1: Name Symbol Qty SegQty LoanQty $Price CAD $Value $Cost (most common)
                # Pattern 2: Name Symbol Qty SegQty LoanQty $Price $Value $Cost (no CAD after price)
                match = re.match(
                    r"^(.+?)\s+([A-Z]{2,6})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\$?([\d,]+(?:\.\d{1,2})?)(?:\s+CAD)?\s*\$?([\d,]+(?:\.\d{1,2})?)\s*\$?([\d,]+(?:\.\d{1,2})?)",
                    line,
                )
                if match:
                    try:
                        holdings.append(
                            {
                                "symbol": match.group(2),
                                "name": match.group(1).strip(),
                                "quantity": Decimal(match.group(3)),
                                "segregated_quantity": Decimal(match.group(4)),
                                "price": Decimal(match.group(6).replace(",", "")),
                                "market_value": Decimal(
                                    match.group(7).replace(",", "")
                                ),
                                "book_cost": Decimal(match.group(8).replace(",", "")),
                            }
                        )
                    except:
                        pass

        return holdings

    def _extract_cash_summary(self, text: str) -> Dict:
        """Extract cash summary from Portfolio Cash section."""
        cash = {
            "last_statement_cash_balance": Decimal("0"),
            "total_cash_paid_in": Decimal("0"),
            "total_cash_paid_out": Decimal("0"),
            "closing_cash_balance": Decimal("0"),
            "contributions_ytd": Decimal("0"),
            "deposits": Decimal("0"),
            "proceeds_from_sales": Decimal("0"),
            "dividends": Decimal("0"),
            "interest_earned": Decimal("0"),
            "fees": Decimal("0"),
            "withdrawals": Decimal("0"),
        }

        patterns = {
            "last_statement_cash_balance": r"Last Statement Cash Balance\s+\$?([\d,.\-]+)",
            "total_cash_paid_in": r"Total Cash Paid In\s+\$?([\d,.\-]+)",
            "total_cash_paid_out": r"Total Cash Paid Out\s+\$?([\d,.\-]+)",
            "closing_cash_balance": r"Closing Cash Balance\s+\$?([\d,.\-]+)",
            "contributions_ytd": r"Contributions\s*\([^)]*\):\s*\$?([\d,.\-]+)",
            "deposits": r"Deposits\s+\$?([\d,.\-]+)",
            "proceeds_from_sales": r"sales\s+\$?([\d,.\-]+)",
            "dividends": r"Dividends\s+\$?([\d,.\-]+)",
            "interest_earned": r"Interest Earned\s+\$?([\d,.\-]+)",
            "withdrawals": r"Withdrawals\s+\$?([\d,.\-]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    cash[key] = Decimal(
                        match.group(1).replace("$", "").replace(",", "")
                    )
                except:
                    pass

        return cash

    def _extract_transactions_from_tables(
        self, tables: List, full_text: str
    ) -> List[Dict]:
        """Extract transactions from tables."""
        transactions = []

        for table in tables:
            if not table or len(table) < 2:
                continue

            if self._is_transaction_table(table):
                headers = [str(h).lower().strip() if h else "" for h in table[0]]

                if "date" not in headers or "transaction" not in headers:
                    continue

                for row in table[1:]:
                    if not row or len(row) < 3:
                        continue

                    tx = self._parse_table_row(headers, row)
                    if tx:
                        transactions.append(tx)

        return transactions

    def _is_transaction_table(self, table: List) -> bool:
        """Check if table looks like transaction data."""
        if not table or len(table) < 2:
            return False

        first_row = [str(cell).lower() if cell else "" for cell in table[0]]
        return any("date" in cell or "transaction" in cell for cell in first_row)

    def _parse_activity_line(self, line: str) -> Optional[Dict]:
        """Parse a single activity line from the PDF text."""
        import re

        # Pattern with 3 amounts (debit, credit, balance) at the end
        # e.g.: 2026-01-02 BUY EQB - EQB Inc: Bought 0.0219 shares at $104.05 per share (executed at 2025-12-31) $2.28 $0.00 $3.74
        # e.g.: 2026-01-08 BUY XIC - BlackRock iShares Core S&P/TSX Capped Composite Index ETF: $7.96 $0.00 $12.87

        pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2})\s+(\w+)\s+(.+?)\s+\$?([\d,.\-]+)\s+\$?([\d,.\-]+)\s+\$?([\d,.\-]+)$"
        )

        match = pattern.match(line.strip())
        if not match:
            return None

        date_str = match.group(1)
        txn_type = match.group(2).upper()
        description = match.group(3).strip()

        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        # Determine amount from debit/credit columns
        debit_str = match.group(4)
        credit_str = match.group(5)

        try:
            credit_val = (
                Decimal(credit_str.replace("$", "").replace(",", ""))
                if credit_str and credit_str != "-"
                else Decimal("0")
            )
            debit_val = (
                Decimal(debit_str.replace("$", "").replace(",", ""))
                if debit_str and debit_str != "-"
                else Decimal("0")
            )

            if credit_val > 0:
                amount = credit_val
            elif debit_val > 0:
                amount = -debit_val
            else:
                amount = Decimal("0")
        except:
            amount = Decimal("0")

        # Extract symbol from description (e.g., "EQB - EQB Inc:")
        symbol = None
        if "-" in description:
            parts = description.split("-", 1)
            if parts and parts[0].strip():
                symbol_match = re.match(r"^([A-Z]{2,6})\s*$", parts[0].strip())
                if symbol_match:
                    symbol = symbol_match.group(1)

        # Extract shares and price from description
        shares, price = self._extract_shares_price(description, amount)

        # If no shares/price found but this is a BUY with amount, estimate from amount
        # This handles cases where PDF extraction is imperfect
        if txn_type == "BUY" and not shares and amount and amount < 0:
            # Try to find price from the debit amount only (no price info available)
            pass

        # For BUY: amount should be negative (money out)
        # For CONT: amount should be positive (money in)
        if txn_type == "BUY" and amount > 0:
            amount = -abs(amount)

        return {
            "date": date,
            "transaction_type": txn_type
            if txn_type
            in [
                "BUY",
                "SELL",
                "DIV",
                "CONT",
                "WDR",
                "LOAN",
                "RECALL",
                "INTEREST",
                "FPLINT",
            ]
            else "OTHER",
            "symbol": symbol,
            "quantity": shares,
            "price": price,
            "execution_date": date,
            "amount": amount,
            "balance": None,
            "currency": "CAD",
            "description": description,
            "is_drip": False,
            "warnings": [],
        }

    def _detect_account_info(self, text: str):
        """Detect account type and number from PDF text."""
        text_lines = text.split("\n")

        for pattern, account_type in self.ACCOUNT_TYPE_PATTERNS.items():
            if pattern in text.lower():
                self.detected_account_type = account_type
                break

        for pattern in self.ACCOUNT_NUMBER_PATTERNS:
            match = pattern.search(text)
            if match:
                self.detected_account_number = match.group(1)
                break
                if self.detected_account_number:
                    break

        period_match = self.STATEMENT_PERIOD_PATTERN.search(text)
        if period_match:
            try:
                dt = datetime.strptime(period_match.group(1), "%Y-%m-%d")
                self.statement_period = f"{dt.year}-{dt.month:02d}"
            except ValueError:
                pass
        else:
            date_match = self.DATE_PATTERN.search(text)
            if date_match:
                try:
                    dt = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    self.statement_period = f"{dt.year}-{dt.month:02d}"
                except ValueError:
                    pass

    def _extract_transactions_from_text(self, text: str) -> List[Dict]:
        """Extract transactions from text content."""
        transactions = []

        activity_section = False
        for line in text.split("\n"):
            line = line.strip()

            if "Activity - Current period" in line or "Activity" in line:
                activity_section = True
                continue

            if activity_section and line.startswith("Total"):
                break

            if activity_section and line:
                tx = self._parse_activity_line(line)
                if tx:
                    transactions.append(tx)

        return transactions

    def _extract_transactions_from_tables(
        self, tables: List, full_text: str
    ) -> List[Dict]:
        """Extract transactions from tables."""
        transactions = []

        for table in tables:
            if not table or len(table) < 2:
                continue

            if self._is_transaction_table(table):
                headers = [str(h).lower().strip() if h else "" for h in table[0]]

                if "date" not in headers or "transaction" not in headers:
                    continue

                for row in table[1:]:
                    if not row or len(row) < 3:
                        continue

                    tx = self._parse_table_row(headers, row)
                    if tx:
                        transactions.append(tx)

        return transactions

    def _is_transaction_table(self, table: List) -> bool:
        """Check if table looks like transaction data."""
        if not table or len(table) < 2:
            return False

        first_row = [str(cell).lower() if cell else "" for cell in table[0]]
        return any("date" in cell or "transaction" in cell for cell in first_row)

    def _parse_table_row(self, headers: List[str], row: List) -> Optional[Dict]:
        """Parse a table row into transaction dict."""
        try:
            date_idx = headers.index("date") if "date" in headers else 0
            txn_idx = headers.index("transaction") if "transaction" in headers else 1
            desc_idx = headers.index("description") if "description" in headers else 2
            amount_idx = headers.index("amount") if "amount" in headers else 3
            balance_idx = headers.index("balance") if "balance" in headers else -1

            date_str = str(row[date_idx]).strip() if date_idx < len(row) else ""
            txn_type = str(row[txn_idx]).strip() if txn_idx < len(row) else ""
            description = str(row[desc_idx]).strip() if desc_idx < len(row) else ""
            amount_str = str(row[amount_idx]).strip() if amount_idx < len(row) else ""
            balance_str = (
                str(row[balance_idx]).strip()
                if balance_idx > 0 and balance_idx < len(row)
                else ""
            )

            if not date_str or not txn_type:
                return None

            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    date = datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    return None

            amount = (
                Decimal(amount_str.replace("$", "").replace(",", ""))
                if amount_str
                else Decimal("0")
            )
            balance = (
                Decimal(balance_str.replace("$", "").replace(",", ""))
                if balance_str
                else None
            )

            transaction_type = self._map_transaction_type(txn_type)
            if not transaction_type:
                return None

            symbol = self._extract_symbol_from_text(description)
            shares, price = self._extract_shares_price(description, amount)
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
                "currency": "CAD",
                "description": description,
                "is_drip": False,
                "warnings": [],
            }

        except (IndexError, ValueError) as e:
            return None

    def _map_transaction_type(self, txn_type: str) -> Optional[str]:
        """Map PDF transaction type to standard type."""
        mapping = {
            "buy": "BUY",
            "sell": "SELL",
            "dividend": "DIV",
            "div": "DIV",
            "contribution": "CONT",
            "cont": "CONT",
            "withdrawal": "WDR",
            "wdr": "WDR",
            "loan": "LOAN",
            "recall": "RECALL",
            "interest": "INTEREST",
        }

        return mapping.get(txn_type.lower(), txn_type.upper())

    def _extract_symbol_from_text(self, text: str) -> Optional[str]:
        """Extract stock symbol from text."""
        match = re.search(r"^([A-Z]{2,6})\s*[-:]", text)
        if match:
            return match.group(1)
        return None

    def _extract_shares_price(
        self, text: str, amount: Optional[Decimal] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Extract shares and price from text."""
        shares = None
        price = None

        # Pattern: "Bought 0.0219 shares at $104.05 per share" or "at $2,400.00 per share"
        match = re.search(
            r"(?:bought|sold)\s+([\d.]+)\s+shares?\s+at\s+\$?([\d,]+\.?\d*)(?:\s+per\s+share)?",
            text,
            re.IGNORECASE,
        )
        if match:
            try:
                shares = Decimal(match.group(1))
                price = Decimal(match.group(2).replace(",", ""))
                return shares, price
            except (ValueError, IndexError):
                pass
                
        match_no_price = re.search(
            r"(?:bought|sold)\s+([\d.]+)\s+shares?",
            text,
            re.IGNORECASE,
        )
        if match_no_price:
            try:
                shares = Decimal(match_no_price.group(1))
            except (ValueError, IndexError):
                pass

        if shares and shares > 0 and not price and amount:
            price = round(abs(amount) / shares, 4)

        return shares, price

    def _extract_execution_date(self, text: str) -> Optional[datetime]:
        """Extract execution date from text."""
        match = re.search(r"\(executed\s+at\s+(\d{4}-\d{2}-\d{2})\)", text)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
        return None

    def _apply_drip_detection(self, transactions: List[Dict]) -> List[Dict]:
        """Apply DRIP detection to transactions."""
        transactions = sorted(transactions, key=lambda x: x["date"])

        for i, tx in enumerate(transactions):
            if tx["transaction_type"] == "DIV":
                symbol = tx["symbol"]
                div_date = tx["date"]
                div_amount = abs(tx["amount"])

                for j in range(i + 1, min(i + 5, len(transactions))):
                    next_tx = transactions[j]

                    if (
                        next_tx["transaction_type"] == "BUY"
                        and next_tx["symbol"] == symbol
                        and (next_tx["date"] - div_date).days <= 5
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
                                break

        return transactions

    def _build_result(self, transactions: List[Dict], full_text: str) -> Dict:
        """Build the final parsed result."""
        summary = {
            "total_transactions": len(transactions),
            "buys": len([t for t in transactions if t["transaction_type"] == "BUY"]),
            "sells": len([t for t in transactions if t["transaction_type"] == "SELL"]),
            "dividends": len(
                [t for t in transactions if t["transaction_type"] == "DIV"]
            ),
            "drips": len([t for t in transactions if t["transaction_type"] == "DRIP"]),
        }

        return {
            "detected_account_type": self.detected_account_type,
            "detected_account_number": self.detected_account_number,
            "statement_period": self.statement_period,
            "transactions": transactions,
            "summary": summary,
            "errors": [],
        }


def parse_pdf_file(file_path: str) -> Dict:
    """Convenience function to parse a PDF file."""
    parser = PDFStatementParser()
    return parser.parse_pdf_file(file_path)


def parse_pdf_content(content: bytes) -> Dict:
    """Convenience function to parse PDF from bytes."""
    parser = PDFStatementParser()
    return parser.parse_pdf_content(content)
