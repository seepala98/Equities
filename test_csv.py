import sys

sys.path.insert(0, "/app")
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
import django

django.setup()

from stocks.portfolio_parser import AccountStatementParser

# Read CSV
with open("/tmp/test.csv", "rb") as f:
    content = f.read()
content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8")

# Parse
parser = AccountStatementParser()
result = parser.parse_csv_content(content)

print(f"Transactions: {len(result.get('transactions', []))}")
for tx in result.get("transactions", [])[:5]:
    print(
        f"  {tx.get('date')} {tx.get('transaction_type')} {tx.get('symbol')} qty={tx.get('quantity')} price={tx.get('price')}"
    )
print()
print("Warnings:")
count = 0
for tx in result.get("transactions", []):
    if tx.get("warnings"):
        count += 1
        print(f"  {tx.get('symbol')}: {tx.get('warnings')}")
if count == 0:
    print("  No warnings!")
