from __future__ import annotations

import re

from app.models import TransactionIn


_AMOUNT_RE = re.compile(r"\$?(-?\d+(?:\.\d{1,2})?)")


def parse_transaction_line(line: str) -> TransactionIn:
    """Parse a free-form line such as 'Paid $12.50 at Corner Cafe.'"""
    amount_match = _AMOUNT_RE.search(line)
    if not amount_match:
        raise ValueError("Could not parse amount from line")

    amount = float(amount_match.group(1))
    description = line.strip()
    return TransactionIn(description=description, amount=amount)
