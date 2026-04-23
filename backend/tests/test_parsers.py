from app.parsers.csv_parser import parse_csv_text
from app.parsers.text_parser import parse_transaction_line


def test_parse_transaction_line_corner_cafe() -> None:
    tx = parse_transaction_line("Paid $12.50 at Corner Cafe.")
    assert tx.amount == 12.50
    assert "Corner Cafe" in tx.description


def test_parse_csv_text_minimum_headers() -> None:
    payload = "description,amount\nStarbucks,-5.25\nNetflix,-16.99\n"
    txs = parse_csv_text(payload)
    assert len(txs) == 2
    assert txs[0].description == "Starbucks"
    assert txs[1].amount == -16.99


def test_parse_csv_text_product_alias_headers() -> None:
    payload = "product_name,price\nSample Product 1,12.50\nSample Product 2,24.00\n"
    txs = parse_csv_text(payload)
    assert len(txs) == 2
    assert txs[0].description == "Sample Product 1"
    assert txs[0].amount == 12.50
