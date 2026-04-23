from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Sequence

import pytest
import yaml
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

import app.main as main_module
from app.evaluation.metrics import correctness_percent
from app.parsers.csv_parser import parse_csv_text
from app.evaluation.run_eval import run_evaluation
from app.rules.engine import RuleEngine


scenarios("features/expense_categorization.feature")
scenarios("features/merchant_memory.feature")
scenarios("features/fuzzy_matching.feature")


RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "rules.yaml"
DEFAULT_MERCHANT_MEMORY_PATH = Path(__file__).resolve().parents[1] / "config" / "merchant_memory.yaml"
DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "samples" / "expense_categorizer_realistic_transactions_1000.csv"


def _table_to_dicts(datatable: Sequence[Sequence[str]] | None) -> list[dict[str, str]]:
    if not datatable:
        raise AssertionError("Expected a Gherkin data table")
    headers = [str(cell).strip() for cell in datatable[0]]
    rows: list[dict[str, str]] = []
    for row in datatable[1:]:
        values = [str(cell).strip() for cell in row]
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


@pytest.fixture
def bdd_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    temp_memory_path = tmp_path / "merchant_memory.yaml"
    if DEFAULT_MERCHANT_MEMORY_PATH.exists():
        temp_memory_path.write_text(DEFAULT_MERCHANT_MEMORY_PATH.read_text())
    monkeypatch.setattr(main_module, "MERCHANT_MEMORY_PATH", temp_memory_path)
    main_module.engine = RuleEngine.from_yaml(main_module.RULES_PATH, main_module.MERCHANT_MEMORY_PATH)
    return {}


@pytest.fixture
def client(bdd_context: dict[str, Any]) -> TestClient:
    return TestClient(main_module.app)


@given("the expense categorizer service is running")
def service_is_running(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@given("keyword rules are loaded")
def keyword_rules_are_loaded() -> None:
    main_module.engine = RuleEngine.from_yaml(main_module.RULES_PATH, main_module.MERCHANT_MEMORY_PATH)
    assert main_module.engine.rules


@given("a labeled validation dataset is available")
def labeled_validation_dataset_is_available() -> None:
    assert DATASET_PATH.exists()


@given("merchant memory contains \"my local cafe\" mapped to \"Food\"")
def merchant_memory_contains_local_cafe() -> None:
    main_module._save_merchant_memory({"my local cafe": "Food"})
    main_module.reload_rules()


@given("merchant memory contains \"starbucks coffee\" mapped to \"Food\"")
def merchant_memory_contains_starbucks() -> None:
    main_module._save_merchant_memory({"starbucks coffee": "Food"})
    main_module.reload_rules()


@given("a CSV file containing the following transactions")
def csv_file_containing_transactions(bdd_context: dict[str, Any], datatable: Sequence[Sequence[str]]) -> None:
    rows = _table_to_dicts(datatable)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    bdd_context["csv_content"] = buffer.getvalue().encode("utf-8")


@when(parsers.parse("I submit the transaction text \"{transaction_text}\""))
def submit_transaction_text(client: TestClient, bdd_context: dict[str, Any], transaction_text: str) -> None:
    response = client.post("/categorize-text", json=[transaction_text])
    bdd_context["response"] = response
    assert response.status_code == 200


@when("I upload the CSV file")
def upload_csv_file(client: TestClient, bdd_context: dict[str, Any]) -> None:
    response = client.post(
        "/upload-csv",
        files={"file": ("transactions.csv", bdd_context["csv_content"], "text/csv")},
    )
    bdd_context["response"] = response
    assert response.status_code == 200


@when(parsers.parse("I upsert merchant memory with merchant \"{merchant}\" and category \"{category}\""))
def upsert_merchant_memory(client: TestClient, bdd_context: dict[str, Any], merchant: str, category: str) -> None:
    response = client.post("/merchant-memory/upsert", json={"merchant": merchant, "category": category})
    bdd_context["response"] = response


@when(parsers.parse("I categorize a structured transaction with description \"{description}\" and amount {amount:g}"))
def categorize_structured_transaction(
    client: TestClient,
    bdd_context: dict[str, Any],
    description: str,
    amount: float,
) -> None:
    response = client.post(
        "/categorize",
        json={
            "transactions": [
                {
                    "description": description,
                    "amount": amount,
                    "currency": "USD",
                }
            ]
        },
    )
    bdd_context["response"] = response
    assert response.status_code == 200


@when(parsers.parse("I run the evaluation gate with a threshold of {threshold:g} percent"))
def run_evaluation_gate(bdd_context: dict[str, Any], threshold: float) -> None:
    transactions = parse_csv_text(DATASET_PATH.read_text())
    engine = RuleEngine.from_yaml(RULES_PATH, DEFAULT_MERCHANT_MEMORY_PATH)
    predictions = [engine.categorize(tx) for tx in transactions]
    bdd_context["evaluation"] = {
        "exit_code": run_evaluation(DATASET_PATH, RULES_PATH, threshold),
        "correctness_percent": correctness_percent(predictions, transactions),
    }


@then(parsers.parse("the merchant memory response should normalize the merchant to \"{normalized_merchant}\""))
def merchant_memory_response_is_normalized(bdd_context: dict[str, Any], normalized_merchant: str) -> None:
    response = bdd_context["response"]
    assert response.status_code == 200
    assert response.json()["normalized_merchant"] == normalized_merchant


@then(parsers.parse("the category should be \"{category}\""))
def category_should_be(bdd_context: dict[str, Any], category: str) -> None:
    response = bdd_context["response"]
    body = response.json()
    if "category" in body:
        assert body["category"] == category
        return
    assert body["transactions"][0]["predicted_category"] == category


@then(parsers.parse("the transaction should be categorized as \"{category}\""))
def transaction_should_be_categorized_as(bdd_context: dict[str, Any], category: str) -> None:
    response = bdd_context["response"]
    assert response.status_code == 200
    assert response.json()["transactions"][0]["predicted_category"] == category


@then(parsers.parse("the matched rule id should be \"{rule_id}\""))
def matched_rule_id_should_be(bdd_context: dict[str, Any], rule_id: str) -> None:
    response = bdd_context["response"]
    assert response.json()["transactions"][0]["matched_rule_id"] == rule_id


@then(parsers.parse("the matched rule id should start with \"{prefix}\""))
def matched_rule_id_should_start_with(bdd_context: dict[str, Any], prefix: str) -> None:
    response = bdd_context["response"]
    matched_rule_id = response.json()["transactions"][0]["matched_rule_id"]
    assert matched_rule_id is not None
    assert matched_rule_id.startswith(prefix)


@then(parsers.parse("the transaction status should be \"{status}\""))
def transaction_status_should_be(bdd_context: dict[str, Any], status: str) -> None:
    response = bdd_context["response"]
    assert response.json()["transactions"][0]["status"] == status


@then(parsers.parse("all {count:d} transactions should be categorized"))
def all_transactions_should_be_categorized(bdd_context: dict[str, Any], count: int) -> None:
    response = bdd_context["response"]
    body = response.json()
    assert body["categorized_count"] == count
    assert body["uncategorized_count"] == 0


@then(parsers.parse("the coverage percent should be {coverage:g}"))
def coverage_percent_should_be(bdd_context: dict[str, Any], coverage: float) -> None:
    response = bdd_context["response"]
    assert response.json()["coverage_percent"] == coverage


@then(parsers.parse("the request should fail with status {status_code:d}"))
def request_should_fail_with_status(bdd_context: dict[str, Any], status_code: int) -> None:
    response = bdd_context["response"]
    assert response.status_code == status_code


@then(parsers.parse("the error message should mention \"{message}\""))
def error_message_should_mention(bdd_context: dict[str, Any], message: str) -> None:
    response = bdd_context["response"]
    assert message in response.json()["detail"]


@then("the evaluation should pass")
def evaluation_should_pass(bdd_context: dict[str, Any]) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation["exit_code"] == 0


@then(parsers.parse("the correctness percent should be at least {threshold:g}"))
def correctness_percent_should_be_at_least(bdd_context: dict[str, Any], threshold: float) -> None:
    evaluation = bdd_context["evaluation"]
    assert evaluation["correctness_percent"] >= threshold
