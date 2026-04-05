import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/web")

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

import django

django.setup()

from stocks.portfolio_parser import AccountStatementParser
from stocks.pdf_parser import PDFStatementParser

# Parse CSV
csv_parser = AccountStatementParser()
csv_result = csv_parser.parse_csv_content(open("/tmp/test.csv").read())

print("=== CSV TRANSACTIONS ===")
for tx in csv_result.get("transactions", [])[:5]:
    print(
        f"  {tx.get('date')} {tx.get('transaction_type')} {tx.get('symbol')} qty={tx.get('quantity')} price={tx.get('price')}"
    )

print()
print("=== CSV SUMMARY ===")
print(csv_result.get("summary"))

# Check if DRIP detection is flagging
print()
print("=== DRIP WARNINGS ===")
found = False
for tx in csv_result.get("transactions", []):
    if tx.get("warnings"):
        found = True
        print(f"  {tx.get('symbol')}: {tx.get('warnings')}")
if not found:
    print("  No warnings!")
