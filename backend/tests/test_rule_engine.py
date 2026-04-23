from pathlib import Path

from app.models import MatchType, Rule, TransactionIn
from app.rules.engine import RuleEngine


RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "rules.yaml"


def test_rule_engine_starbucks_food() -> None:
    engine = RuleEngine.from_yaml(RULES_PATH)
    result = engine.categorize(TransactionIn(description="STARBUCKS #1234", amount=-5.20))
    assert result.predicted_category == "Food"


def test_rule_engine_landlord_amount_bound() -> None:
    engine = RuleEngine.from_yaml(RULES_PATH)
    result = engine.categorize(TransactionIn(description="Landlord Corp monthly", amount=1200.00))
    assert result.predicted_category == "Rent"


def test_overlapping_contains_uses_priority() -> None:
    engine = RuleEngine(
        [
            Rule(
                rule_id="food_cafe_generic",
                category="Food",
                match_type=MatchType.CONTAINS,
                pattern="cafe",
                priority=80,
                active=True,
            ),
            Rule(
                rule_id="food_corner_cafe_specific",
                category="Food",
                match_type=MatchType.CONTAINS,
                pattern="corner cafe",
                priority=100,
                active=True,
            ),
        ]
    )
    result = engine.categorize(TransactionIn(description="Paid at Corner Cafe", amount=12.5))
    assert result.matched_rule_id == "food_corner_cafe_specific"


def test_merchant_memory_exact_match_when_rules_do_not_match() -> None:
    engine = RuleEngine(
        [
            Rule(
                rule_id="some_other_rule",
                category="Food",
                match_type=MatchType.CONTAINS,
                pattern="different merchant",
                priority=100,
                active=True,
            )
        ],
        merchant_memory={"acme payroll deposit": "Uncategorized"},
    )
    result = engine.categorize(TransactionIn(description="ACME Payroll Deposit", amount=2200.0))
    assert result.predicted_category == "Uncategorized"
    assert result.matched_rule_id == "merchant_memory_exact"


def test_fuzzy_fallback_for_typo_description() -> None:
    engine = RuleEngine(
        [],
        merchant_memory={"starbucks coffee": "Food"},
    )
    result = engine.categorize(TransactionIn(description="Starbuks Cofee", amount=-8.0))
    assert result.predicted_category == "Food"
    assert result.matched_rule_id is not None
    assert result.matched_rule_id.startswith("fuzzy:")
