from pathlib import Path
import pandas as pd
from src.excel_branch_merger.merger import process_folder

CONFIG = {
    "canonical_columns": {"customer_name": ["Customer"], "sale_date": ["Date"], "amount": ["Amount"], "invoice_number": ["Invoice"]},
    "required_fields": ["customer_name", "sale_date", "amount"],
    "duplicate_key": ["customer_name", "sale_date", "amount", "invoice_number"],
    "date_formats": ["%Y-%m-%d"],
}

def test_missing_duplicate_key_column_never_shrinks_key(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({"Customer": ["Alice", "Alice"], "Date": ["2026-08-01", "2026-08-01"], "Amount": [100, 100]}).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert len(consolidated) == 2
    assert result.duplicates_removed == 0
    assert "WARN incomplete duplicate key" in result.log_path.read_text(encoding="utf-8")


def test_blank_key_value_is_kept_but_complete_duplicate_is_removed(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({
        "Customer": ["Alice", "Alice", "Bob", "Bob"],
        "Date": ["2026-08-01"] * 4,
        "Amount": [100, 100, 200, 200],
        "Invoice": [None, None, "B-1", "B-1"],
    }).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert len(consolidated) == 3
    assert result.duplicates_removed == 1


def test_whitespace_key_value_is_incomplete(tmp_path: Path) -> None:
    inp = tmp_path / "input"; inp.mkdir(); out = tmp_path / "output"
    pd.DataFrame({
        "Customer": ["Alice", "Alice"],
        "Date": ["2026-08-01", "2026-08-01"],
        "Amount": [100, 100],
        "Invoice": ["   ", "   "],
    }).to_excel(inp / "sales.xlsx", index=False)
    result = process_folder(inp, out, CONFIG)
    consolidated = pd.read_excel(result.report_path, sheet_name="Consolidated")
    assert len(consolidated) == 2
    assert result.duplicates_removed == 0
