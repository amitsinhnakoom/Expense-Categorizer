from app.evaluation.metrics import correctness_percent, coverage_percent
from app.models import TransactionIn, TransactionOut


def test_metrics_coverage_and_correctness() -> None:
    source = [
        TransactionIn(description="Starbucks", amount=-5.0, labeled_category="Food"),
        TransactionIn(description="Unknown", amount=-9.0, labeled_category="Uncategorized"),
    ]
    predicted = [
        TransactionOut(
            raw_description="Starbucks",
            normalized_description="starbucks",
            amount=-5.0,
            currency="USD",
            predicted_category="Food",
            matched_rule_id="food",
            status="categorized",
        ),
        TransactionOut(
            raw_description="Unknown",
            normalized_description="unknown",
            amount=-9.0,
            currency="USD",
            predicted_category="Uncategorized",
            matched_rule_id=None,
            status="uncategorized",
        ),
    ]

    assert coverage_percent(predicted) == 50.0
    assert correctness_percent(predicted, source) == 100.0
