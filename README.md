# Expense Categorizer

Expense Categorizer is a FastAPI-based transaction tagging service with a web UI.
It classifies uploaded raw transactions (CSV or text) into categories such as Food, Rent, Luxuries, Utilities, and more.

## Core Capabilities

- Upload CSV transactions and get row-level predicted category + summary metrics.
- Parse free-form text lines (for quick checks and demos).
- Deterministic rules engine with explicit precedence.
- Merchant memory for persistent exact merchant-to-category mapping.
- Fuzzy fallback matching for typo/variation resilience.
- Coverage and correctness metrics in API responses.

## Matching Logic (Business Algorithm)

The categorization pipeline runs in this order:

1. Description normalization
- Lowercase
- Remove punctuation and non-word symbols
- Remove store numeric suffixes (example: `#1234`)
- Collapse repeated whitespace

2. Deterministic rule matching
- Rule source: `backend/config/rules.yaml`
- Contains rules are matched via trie-based multi-pattern scan (Aho-Corasick style)
- Exact and regex rules are evaluated directly

3. Rule candidate selection
- Keep only active rules
- Enforce `amount_min` / `amount_max` when present

4. Rule winner selection
- Match type precedence: `exact` > `contains` > `regex`
- Tie-breakers: higher `priority`, then longer `pattern`

5. Merchant memory exact fallback
- If no rule matched, try normalized merchant exact lookup
- Memory source: `backend/config/merchant_memory.yaml`

6. Fuzzy fallback
- If still unmatched, compare normalized description against memory terms + contains patterns
- Uses `rapidfuzz` token-set similarity
- Applies thresholded confidence before tagging

7. Final fallback
- If no confident match: `Uncategorized`

## Setup and Run

### Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend default URL: `http://127.0.0.1:8000`

### Start without port conflicts

From project root:

```bash
./scripts/start_backend.sh
```

If 8000 is in use, the script auto-selects the next free port.
You can provide a preferred start port:

```bash
./scripts/start_backend.sh 8001
```

Compatibility wrappers still work:

```bash
./start_backend.sh
./launch.command
```

## API Documentation

Interactive docs:

- Swagger UI: `/docs`
- ReDoc: `/redoc`

### `GET /health`

Purpose: service health check.

Example response:

```json
{"status": "ok"}
```

### `GET /`

Purpose: serves the frontend UI page.

### `POST /rules/reload`

Purpose: reloads rules and merchant memory from config files.

Example response:

```json
{"rule_count": 4}
```

### `GET /merchant-memory`

Purpose: returns current merchant-memory map.

Example response:

```json
{
	"merchant_memory": {
		"starbucks coffee": "Food",
		"netflix subscription": "Luxuries"
	}
}
```

### `POST /merchant-memory/upsert`

Purpose: add or update a merchant-memory mapping, persist to YAML, and reload engine.

Request body:

```json
{
	"merchant": "My Local Cafe",
	"category": "Food"
}
```

Response body:

```json
{
	"merchant": "My Local Cafe",
	"normalized_merchant": "my local cafe",
	"category": "Food"
}
```

### `POST /categorize`

Purpose: categorize structured transaction payload.

Request body:

```json
{
	"transactions": [
		{
			"date": "2026-04-22",
			"description": "Paid $12.50 at Corner Cafe.",
			"amount": 12.5,
			"currency": "USD",
			"labeled_category": "Food"
		}
	]
}
```

Response highlights:

- `transactions[]`: per-row tagging output
- `coverage_percent`
- `correctness_percent` (only when labels are provided)

### `POST /categorize-text`

Purpose: categorize raw transaction text lines.

Request body:

```json
[
	"Paid $12.50 at Corner Cafe.",
	"Netflix subscription $16.99"
]
```

### `POST /upload-csv`

Purpose: upload CSV file and categorize it.

Input:

- Multipart file with `.csv` extension
- Required semantic columns: description + amount
- Supported aliases:
	- Description: `description`, `details`, `merchant`, `narrative`, `product_name`, `name`, `item`, `title`
	- Amount: `amount`, `debit`, `withdrawal`, `price`, `cost`, `total`

## Module and Function Documentation

### `backend/app/main.py`

- `health()`: health endpoint.
- `serve_ui()`: serves frontend index page.
- `reload_rules()`: reloads rule engine from YAML configs.
- `_load_merchant_memory()`: reads merchant memory YAML.
- `_save_merchant_memory(memory)`: writes merchant memory YAML.
- `get_merchant_memory()`: returns in-memory/persisted merchant map.
- `upsert_merchant_memory(payload)`: validates, normalizes, persists mapping, reloads engine.
- `categorize(payload)`: main structured categorization endpoint.
- `categorize_text(lines)`: text-line convenience endpoint.
- `upload_csv(file)`: CSV ingestion + categorization endpoint.

### `backend/app/rules/engine.py`

- `RuleEngine.__init__(rules, merchant_memory)`: initializes rule and fallback structures.
- `RuleEngine.from_yaml(path, merchant_memory_path)`: loads rules + merchant memory from YAML.
- `RuleEngine.categorize(tx)`: end-to-end categorization for one transaction.
- `RuleEngine._matches(rule, normalized_description)`: exact/regex matcher.
- `RuleEngine._is_rule_applicable(rule, amount)`: active + amount-band gate.
- `RuleEngine._build_contains_automaton()`: builds trie/failure links for contains patterns.
- `RuleEngine._matched_contains_rules(text)`: multi-pattern contains lookup.
- `RuleEngine._build_fuzzy_dictionary()`: prepares fuzzy candidate terms.
- `RuleEngine._fuzzy_category(normalized_description)`: fuzzy fallback category selection.
- `RuleEngine._match_rank(rule)`: match-type ranking helper.
- `RuleEngine._choose_best(candidates)`: deterministic winner selection.

### `backend/app/parsers/csv_parser.py`

- `_find_header_index(headers, candidates)`: locate matching column index by aliases.
- `parse_csv_text(csv_text)`: convert CSV rows into `TransactionIn` list.

### `backend/app/parsers/text_parser.py`

- `parse_transaction_line(line)`: extract amount and description from free text line.

### `backend/app/normalization/cleaner.py`

- `normalize_description(text)`: canonical normalization before matching.

### `backend/app/evaluation/metrics.py`

- `coverage_percent(categorized)`: categorized-row coverage metric.
- `correctness_percent(categorized, source)`: label-against-ground-truth correctness.

### `backend/app/evaluation/run_eval.py`

- `run_evaluation(dataset_path, rules_path, threshold)`: computes metrics and pass/fail gate.
- `main()`: CLI argument entrypoint for evaluation runner.

### `backend/app/models.py`

Data contracts used across parser, engine, and API.

- `MatchType`
- `TransactionIn`
- `TransactionOut`
- `Rule`
- `CategorizeRequest`
- `CategorizeResponse`
- `MerchantMemoryUpsertRequest`
- `MerchantMemoryUpsertResponse`

### `backend/app/rules/schema.py`

- `RulesConfig`: pydantic schema wrapper for rule list payload.

## Project Layout

- `backend/`: FastAPI app, config, tests, evaluation utilities.
- `frontend/`: browser UI.
- `scripts/`: launch and run scripts.
- `data/samples/`: sample datasets.
- `logs/`: runtime launcher logs.

## Tests

```bash
cd backend
pytest -q
```

Acceptance scenario included:

- Input: `Paid $12.50 at Corner Cafe.`
- Expected category: `Food`

## Evaluation Gate (80% correctness)

```bash
cd backend
python -m app.evaluation.run_eval --threshold 80
```

Expected behavior:

- Prints dataset rows, coverage, correctness, and threshold.
- Exits success when correctness is at least threshold.
