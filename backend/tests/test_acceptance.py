from pathlib import Path

from app.models import TransactionIn
from app.rules.engine import RuleEngine


RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "rules.yaml"


def test_acceptance_corner_cafe_food() -> None:
    engine = RuleEngine.from_yaml(RULES_PATH)
    tx = TransactionIn(description="Paid $12.50 at Corner Cafe.", amount=12.50)
    result = engine.categorize(tx)
    assert result.predicted_category == "Food"
