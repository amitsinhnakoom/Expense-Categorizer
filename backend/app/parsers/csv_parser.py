from __future__ import annotations

import csv
from io import StringIO

from app.models import TransactionIn


DATE_HEADERS = {"date", "transaction date", "posted date"}
DESC_HEADERS = {
    "description",
    "details",
    "merchant",
    "narrative",
    "product_name",
    "name",
    "item",
    "title",
}
AMOUNT_HEADERS = {"amount", "debit", "withdrawal", "price", "cost", "total"}
CURRENCY_HEADERS = {"currency"}
LABEL_HEADERS = {"label", "category", "labeled_category"}


def _find_header_index(headers: list[str], candidates: set[str]) -> int | None:
    lowered = [h.strip().lower() for h in headers]
    for i, name in enumerate(lowered):
        if name in candidates:
            return i
    return None


def parse_csv_text(csv_text: str) -> list[TransactionIn]:
    reader = csv.reader(StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return []

    headers = rows[0]
    date_idx = _find_header_index(headers, DATE_HEADERS)
    desc_idx = _find_header_index(headers, DESC_HEADERS)
    amount_idx = _find_header_index(headers, AMOUNT_HEADERS)
    currency_idx = _find_header_index(headers, CURRENCY_HEADERS)
    label_idx = _find_header_index(headers, LABEL_HEADERS)

    if desc_idx is None or amount_idx is None:
        raise ValueError("CSV must include description and amount columns")

    transactions: list[TransactionIn] = []
    for row in rows[1:]:
        if not row or len(row) <= max(desc_idx, amount_idx):
            continue
        amount = float(row[amount_idx].replace("$", "").strip())
        tx = TransactionIn(
            date=row[date_idx] if date_idx is not None and row[date_idx] else None,
            description=row[desc_idx].strip(),
            amount=amount,
            currency=(row[currency_idx].strip() if currency_idx is not None and row[currency_idx] else "USD"),
            labeled_category=(row[label_idx].strip() if label_idx is not None and row[label_idx] else None),
        )
        transactions.append(tx)

    return transactions
