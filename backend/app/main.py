from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.evaluation.metrics import correctness_percent, coverage_percent
from app.models import (
    CategorizeRequest,
    CategorizeResponse,
    MerchantMemoryUpsertRequest,
    MerchantMemoryUpsertResponse,
    TransactionIn,
)
from app.normalization.cleaner import normalize_description
from app.parsers.csv_parser import parse_csv_text
from app.parsers.text_parser import parse_transaction_line
from app.rules.engine import RuleEngine

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent
RULES_PATH = BASE_DIR / "config" / "rules.yaml"
MERCHANT_MEMORY_PATH = BASE_DIR / "config" / "merchant_memory.yaml"
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="Expense Categorizer")
engine = RuleEngine.from_yaml(RULES_PATH, MERCHANT_MEMORY_PATH)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def serve_ui() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


# Serve frontend static files; mounted after API routes so /health etc. take priority.
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="ui")


@app.post("/rules/reload")
def reload_rules() -> dict[str, int]:
    global engine
    engine = RuleEngine.from_yaml(RULES_PATH, MERCHANT_MEMORY_PATH)
    return {"rule_count": len(engine.rules)}


def _load_merchant_memory() -> dict[str, str]:
    if not MERCHANT_MEMORY_PATH.exists():
        return {}
    payload = yaml.safe_load(MERCHANT_MEMORY_PATH.read_text()) or {}
    memory = payload.get("merchant_memory", {})
    if not isinstance(memory, dict):
        return {}
    return {str(k): str(v) for k, v in memory.items()}


def _save_merchant_memory(memory: dict[str, str]) -> None:
    MERCHANT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MERCHANT_MEMORY_PATH.write_text(
        yaml.safe_dump({"merchant_memory": memory}, sort_keys=True),
    )


@app.get("/merchant-memory")
def get_merchant_memory() -> dict[str, dict[str, str]]:
    return {"merchant_memory": _load_merchant_memory()}


@app.post("/merchant-memory/upsert", response_model=MerchantMemoryUpsertResponse)
def upsert_merchant_memory(payload: MerchantMemoryUpsertRequest) -> MerchantMemoryUpsertResponse:
    memory = _load_merchant_memory()
    normalized_merchant = normalize_description(payload.merchant)
    if not normalized_merchant:
        raise HTTPException(status_code=400, detail="merchant must include alphanumeric text")
    memory[normalized_merchant] = payload.category.strip()
    _save_merchant_memory(memory)
    reload_rules()
    return MerchantMemoryUpsertResponse(
        merchant=payload.merchant,
        normalized_merchant=normalized_merchant,
        category=payload.category.strip(),
    )


@app.post("/categorize", response_model=CategorizeResponse)
def categorize(payload: CategorizeRequest) -> CategorizeResponse:
    results = [engine.categorize(tx) for tx in payload.transactions]
    categorized_count = sum(1 for tx in results if tx.status == "categorized")
    uncategorized_count = len(results) - categorized_count

    return CategorizeResponse(
        transactions=results,
        total_count=len(results),
        categorized_count=categorized_count,
        uncategorized_count=uncategorized_count,
        coverage_percent=coverage_percent(results),
        correctness_percent=correctness_percent(results, payload.transactions),
    )


@app.post("/categorize-text", response_model=CategorizeResponse)
def categorize_text(lines: list[str]) -> CategorizeResponse:
    transactions: list[TransactionIn] = []
    for line in lines:
        if not line.strip():
            continue
        transactions.append(parse_transaction_line(line))
    return categorize(CategorizeRequest(transactions=transactions))


@app.post("/upload-csv", response_model=CategorizeResponse)
async def upload_csv(file: UploadFile = File(...)) -> CategorizeResponse:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    content = (await file.read()).decode("utf-8", errors="ignore")
    try:
        transactions = parse_csv_text(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return categorize(CategorizeRequest(transactions=transactions))
