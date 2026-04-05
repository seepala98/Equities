import re
from decimal import Decimal

descriptions = [
    "XIC - BlackRock iShares Core S&P/TSX Capped Composite Index ETF: Bought 0.1548 shares at $51.40 per share (executed at 2026-01-07)",
    "VDY - Vanguard FTSE Canadian: Bought 0.0884 shares at $62.17 per share (executed at 2026-01-08)",
]

for desc in descriptions:
    match = re.search(
        r"(?:bought|sold)\s+([\d.]+)\s+shares?\s+at\s+\$([\d,]+\.?\d*)",
        desc,
        re.IGNORECASE,
    )
    if match:
        print(f"OK: {desc[:50]}...")
        print(f"  Shares: {match.group(1)}, Price: {match.group(2)}")
    else:
        print(f"FAIL: {desc[:50]}...")
