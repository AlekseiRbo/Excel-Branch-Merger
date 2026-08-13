from pathlib import Path
import pandas as pd
from src.excel_branch_merger.merger import process_folder

CONFIG = {
    "canonical_columns": {"customer_name": ["Customer"], "sale_date": ["Date"], "amount": ["Amount"], "invoice_number": ["Invoice"]},
    "required_fields": ["customer_name", "sale_date", "amount"],
    "duplicate_key": ["customer_name", "sale_date", "amount", "invoice_number"],
    "date_formats": ["%Y-%m-%d"],
}

def test_metrics_separate_invalid_duplicates_and_incomplete_keys(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({
        "Customer": ["Alice", "Alice", "Bob", "Cara"],
        "Date": ["2026-08-01", "2026-08-01", "2026-08-02", "bad"],
        "Amount": [100, 100, 200, 300],
        "Invoice": ["A-1", "A-1", None, "C-1"],
    }).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    assert result.total_input_rows == 4
    assert result.valid_rows == 2
    assert result.invalid_rows == 1
    assert result.duplicate_rows == 1
    assert result.incomplete_dedup_key_rows == 1
    assert result.total_rejected_rows == 2
    summary = pd.read_excel(result.report_path, sheet_name="Summary")
    values = dict(zip(summary["Metric"], summary["Value"]))
    assert values["Invalid rows"] == 1
    assert values["Duplicate rows"] == 1
    assert values["Total rejected rows"] == 2

    log_text = result.log_path.read_text(encoding="utf-8")
    assert "SUMMARY Invalid rows: 1" in log_text
    assert "SUMMARY Duplicate rows: 1" in log_text
    assert "SUMMARY Total rejected rows: 2" in log_text
