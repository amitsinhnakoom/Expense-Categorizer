from pathlib import Path

import yaml
from fastapi.testclient import TestClient

import app.main as main_module
from app.rules.engine import RuleEngine


def test_upsert_merchant_memory_and_categorize(monkeypatch, tmp_path: Path) -> None:
    temp_memory_path = tmp_path / "merchant_memory.yaml"
    monkeypatch.setattr(main_module, "MERCHANT_MEMORY_PATH", temp_memory_path)
    main_module.engine = RuleEngine.from_yaml(main_module.RULES_PATH, main_module.MERCHANT_MEMORY_PATH)

    client = TestClient(main_module.app)

    upsert_response = client.post(
        "/merchant-memory/upsert",
        json={"merchant": "My Local Cafe", "category": "Food"},
    )
    assert upsert_response.status_code == 200
    body = upsert_response.json()
    assert body["normalized_merchant"] == "my local cafe"
    assert body["category"] == "Food"

    saved_payload = yaml.safe_load(temp_memory_path.read_text())
    assert saved_payload["merchant_memory"]["my local cafe"] == "Food"

    categorize_response = client.post(
        "/categorize",
        json={
            "transactions": [
                {
                    "description": "MY LOCAL CAFE",
                    "amount": -14.25,
                    "currency": "USD",
                }
            ]
        },
    )
    assert categorize_response.status_code == 200
    tx = categorize_response.json()["transactions"][0]
    assert tx["predicted_category"] == "Food"
    assert tx["matched_rule_id"] == "merchant_memory_exact"


def test_upsert_invalid_merchant_text(monkeypatch, tmp_path: Path) -> None:
    temp_memory_path = tmp_path / "merchant_memory.yaml"
    monkeypatch.setattr(main_module, "MERCHANT_MEMORY_PATH", temp_memory_path)
    main_module.engine = RuleEngine.from_yaml(main_module.RULES_PATH, main_module.MERCHANT_MEMORY_PATH)

    client = TestClient(main_module.app)
    response = client.post(
        "/merchant-memory/upsert",
        json={"merchant": "###", "category": "Food"},
    )
    assert response.status_code == 400
