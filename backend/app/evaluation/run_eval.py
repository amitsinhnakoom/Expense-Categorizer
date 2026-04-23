from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.metrics import correctness_percent, coverage_percent
from app.parsers.csv_parser import parse_csv_text
from app.rules.engine import RuleEngine


BACKEND_DIR = Path(__file__).resolve().parents[2]
MERCHANT_MEMORY_PATH = BACKEND_DIR / "config" / "merchant_memory.yaml"


def run_evaluation(dataset_path: Path, rules_path: Path, threshold: float) -> int:
    transactions = parse_csv_text(dataset_path.read_text())
    engine = RuleEngine.from_yaml(rules_path, MERCHANT_MEMORY_PATH)
    predictions = [engine.categorize(tx) for tx in transactions]

    coverage = coverage_percent(predictions)
    correctness = correctness_percent(predictions, transactions)
    correctness_display = 0.0 if correctness is None else correctness

    print(f"dataset_rows={len(transactions)}")
    print(f"coverage_percent={coverage:.2f}")
    print(f"correctness_percent={correctness_display:.2f}")
    print(f"threshold_percent={threshold:.2f}")

    if correctness is None:
        print("gate=FAIL reason=no_labeled_rows")
        return 1

    if correctness >= threshold:
        print("gate=PASS")
        return 0

    print("gate=FAIL reason=below_threshold")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run rule-engine evaluation against a labeled CSV dataset")
    parser.add_argument(
        "--dataset",
        default=str(BACKEND_DIR / "data" / "validation" / "labeled_transactions.csv"),
        help="Path to labeled CSV dataset",
    )
    parser.add_argument(
        "--rules",
        default=str(BACKEND_DIR / "config" / "rules.yaml"),
        help="Path to YAML rules file",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum correctness percent to pass",
    )
    args = parser.parse_args()

    return run_evaluation(Path(args.dataset), Path(args.rules), args.threshold)


if __name__ == "__main__":
    raise SystemExit(main())
