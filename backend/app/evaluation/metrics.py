from __future__ import annotations

from app.models import TransactionIn, TransactionOut


def coverage_percent(categorized: list[TransactionOut]) -> float:
    if not categorized:
        return 0.0
    covered = sum(1 for tx in categorized if tx.predicted_category != "Uncategorized")
    return (covered / len(categorized)) * 100.0


def correctness_percent(categorized: list[TransactionOut], source: list[TransactionIn]) -> float | None:
    labeled_pairs = [
        (pred, orig)
        for pred, orig in zip(categorized, source)
        if orig.labeled_category is not None and orig.labeled_category != ""
    ]
    if not labeled_pairs:
        return None
    correct = sum(
        1
        for pred, orig in labeled_pairs
        if pred.predicted_category.lower() == orig.labeled_category.lower()
    )
    return (correct / len(labeled_pairs)) * 100.0
